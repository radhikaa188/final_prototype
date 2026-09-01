import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.db.models import Customer, Payment, RecoveryCase, AgentRun, RecoveryAction, User
from app.auth.security import create_access_token
from app.auth.init_users import seed_default_users


@pytest.fixture
def client():
    db = SessionLocal()
    seed_default_users(db)
    ops_user = db.query(User).filter(User.role == "OPS").first()
    token = create_access_token({"sub": ops_user.id, "email": ops_user.email, "role": ops_user.role})
    db.close()
    
    test_client = TestClient(app)
    test_client.headers["Authorization"] = f"Bearer {token}"
    return test_client


def test_1_network_timeout_retry_failure_consistency(client):
    """Test 1 — Network timeout retry failure:
    - Original failure = NETWORK_TIMEOUT
    - Retry = FAILED
    - Gateway message does not unexpectedly become CARD_EXPIRED
    - Payment.failure_reason remains NETWORK_TIMEOUT
    - RecoveryAction.status = FAILED
    - RecoveryCase.status = RE_EVALUATING
    - AgentRun.status = COMPLETED
    """
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]
    customer = Customer(external_customer_id=f"cust_{uid}", name=f"Test Cust {uid}", email=f"cust_{uid}@example.com", lifetime_value=1500.0)
    db.add(customer)
    db.commit()

    # Create payment with gateway_payment_id that will NOT force success
    payment = Payment(customer_id=customer.id, gateway_payment_id=f"pay_live_{uid}", amount=450.0, status="FAILED", failure_reason="NETWORK_TIMEOUT")
    db.add(payment)
    db.commit()

    case = RecoveryCase(
        customer_id=customer.id,
        payment_id=payment.id,
        revenue_at_risk=450.0,
        status="PRIORITIZED",
        next_action="RETRY",
        recommended_action="RETRY",
        priority_score=90.0,
        recovery_probability=0.85,
        root_cause="TRANSIENT_FAILURE"
    )
    db.add(case)
    db.commit()
    case_id = case.id
    db.close()

    # Mock gateway retry failure
    with patch("app.services.gateway_simulator.SimulatedPaymentGateway.process_retry") as mock_retry:
        mock_retry.return_value = {
            "status": "FAILED",
            "transaction_id": f"txn_fail_{uid}",
            "amount_recovered": 0.0,
            "gateway_code": "DECLINED",
            "message": "Payment retry failed: NETWORK_TIMEOUT"
        }
        res = client.post(f"/api/recovery-cases/{case_id}/approve", json={"action": "RETRY"})
        assert res.status_code == 200

    # Verify state transitions & consistency
    db = SessionLocal()
    updated_case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    updated_pay = db.query(Payment).filter(Payment.id == updated_case.payment_id).first()
    last_run = db.query(AgentRun).filter(AgentRun.case_id == case_id).order_by(AgentRun.started_at.desc()).first()
    last_action = db.query(RecoveryAction).filter(RecoveryAction.case_id == case_id).order_by(RecoveryAction.executed_at.desc()).first()

    # 1. Gateway message does not unexpectedly become CARD_EXPIRED
    assert "CARD_EXPIRED" not in last_action.reason
    assert "NETWORK_TIMEOUT" in last_action.reason

    # 2. Payment.failure_reason remains NETWORK_TIMEOUT
    assert updated_pay.failure_reason == "NETWORK_TIMEOUT"
    assert updated_pay.status == "FAILED"

    # 3. RecoveryAction.status = FAILED
    assert last_action.status == "FAILED"

    # 4. RecoveryCase.status = RE_EVALUATING
    assert updated_case.status == "RE_EVALUATING"
    assert updated_case.retry_count == 1

    # 5. AgentRun.status = COMPLETED (operational workflow completion, not payment success)
    assert last_run.status == "COMPLETED"
    assert last_run.final_result == "RETRY_FAILED"
    db.close()


def test_2_successful_network_retry(client):
    """Test 2 — Successful network retry:
    - NETWORK_TIMEOUT -> RETRY -> SUCCESS
    - Payment = SUCCESS
    - RecoveryCase = RECOVERED
    - RecoveryAction = SUCCESS
    - AgentRun = COMPLETED
    """
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]
    customer = Customer(external_customer_id=f"cust_{uid}", name=f"Test Cust {uid}", email=f"cust_{uid}@example.com", lifetime_value=2500.0)
    db.add(customer)
    db.commit()

    payment = Payment(customer_id=customer.id, gateway_payment_id=f"pay_live_{uid}", amount=320.0, status="FAILED", failure_reason="NETWORK_TIMEOUT")
    db.add(payment)
    db.commit()

    case = RecoveryCase(
        customer_id=customer.id,
        payment_id=payment.id,
        revenue_at_risk=320.0,
        status="PRIORITIZED",
        next_action="RETRY",
        recommended_action="RETRY",
        priority_score=85.0,
        recovery_probability=0.80,
        root_cause="TRANSIENT_FAILURE"
    )
    db.add(case)
    db.commit()
    case_id = case.id
    db.close()

    # Mock gateway retry success
    with patch("app.services.gateway_simulator.SimulatedPaymentGateway.process_retry") as mock_retry:
        mock_retry.return_value = {
            "status": "SUCCESS",
            "transaction_id": f"txn_succ_{uid}",
            "amount_recovered": 320.0,
            "gateway_code": "200_OK",
            "message": "Payment captured successfully."
        }
        res = client.post(f"/api/recovery-cases/{case_id}/approve", json={"action": "RETRY"})
        assert res.status_code == 200

    db = SessionLocal()
    updated_case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    updated_pay = db.query(Payment).filter(Payment.id == updated_case.payment_id).first()
    last_run = db.query(AgentRun).filter(AgentRun.case_id == case_id).order_by(AgentRun.started_at.desc()).first()
    last_action = db.query(RecoveryAction).filter(RecoveryAction.case_id == case_id).order_by(RecoveryAction.executed_at.desc()).first()

    assert updated_pay.status == "SUCCESS"
    assert updated_case.status == "RECOVERED"
    assert updated_case.next_action == "NONE"
    assert last_action.status == "SUCCESS"
    assert last_run.status == "COMPLETED"
    db.close()


def test_3_other_transient_failures_consistency(client):
    """Test 3 — Other transient failures:
    - BANK_UNAVAILABLE and GATEWAY_ERROR retry failure messages match original reason.
    """
    for reason in ["BANK_UNAVAILABLE", "GATEWAY_ERROR"]:
        db = SessionLocal()
        uid = uuid.uuid4().hex[:8]
        customer = Customer(external_customer_id=f"cust_{uid}", name=f"Test Cust {uid}", email=f"cust_{uid}@example.com", lifetime_value=1800.0)
        db.add(customer)
        db.commit()

        payment = Payment(customer_id=customer.id, gateway_payment_id=f"pay_live_{uid}", amount=190.0, status="FAILED", failure_reason=reason)
        db.add(payment)
        db.commit()

        case = RecoveryCase(
            customer_id=customer.id,
            payment_id=payment.id,
            revenue_at_risk=190.0,
            status="PRIORITIZED",
            next_action="RETRY",
            recommended_action="RETRY",
            priority_score=75.0,
            recovery_probability=0.75,
            root_cause="TRANSIENT_FAILURE"
        )
        db.add(case)
        db.commit()
        case_id = case.id
        db.close()

        # Real simulator execution with force_success_rate = 0.0 (simulated failure)
        with patch("app.services.gateway_simulator.gateway_simulator.force_success_rate", 0.0):
            res = client.post(f"/api/recovery-cases/{case_id}/approve", json={"action": "RETRY"})
            assert res.status_code == 200

        db = SessionLocal()
        last_action = db.query(RecoveryAction).filter(RecoveryAction.case_id == case_id).order_by(RecoveryAction.executed_at.desc()).first()
        updated_pay = db.query(Payment).filter(Payment.id == case.payment_id).first()

        # Failure message is consistent with original reason
        assert last_action.status == "FAILED"
        assert reason in last_action.reason
        assert updated_pay.failure_reason == reason
        db.close()


def test_4_customer_dependent_failures_interception(client):
    """Test 4 — Customer-dependent failures:
    - CARD_EXPIRED and INSUFFICIENT_FUNDS do not enter gateway retry while customer action is unresolved.
    """
    for reason in ["CARD_EXPIRED", "INSUFFICIENT_FUNDS"]:
        res_gen = client.post("/api/test-mode/generate-payment", json={"amount": 600.0, "failure_reason": reason})
        assert res_gen.status_code == 200
        case_id = res_gen.json()["case_id"]

        db = SessionLocal()
        case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
        assert case.status == "CUSTOMER_ACTION_REQUIRED"
        assert case.next_action == "WAIT_FOR_CUSTOMER_ACTION"
        db.close()

        # Attempting direct execution or approval should NOT call gateway retry
        res_app = client.post(f"/api/recovery-cases/{case_id}/approve", json={"action": "RETRY"})
        assert res_app.status_code == 200
        app_data = res_app.json()
        assert app_data["case_status"] == "CUSTOMER_ACTION_REQUIRED"
        assert app_data["payment_status"] == "FAILED"

        # Verify no gateway recovery action was created
        db = SessionLocal()
        rec_actions = db.query(RecoveryAction).filter(RecoveryAction.case_id == case_id, RecoveryAction.status == "SUCCESS").count()
        assert rec_actions == 0
        db.close()
