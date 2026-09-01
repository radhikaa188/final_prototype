import pytest
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.db.models import Customer, Payment, RecoveryCase, AgentRun, RecoveryAction, User
from app.auth.security import create_access_token
from app.auth.init_users import seed_default_users
from app.services.scheduler_service import scheduler_service


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


def test_1_click_before_retry_after_schedules_without_gateway_call(client):
    """Test 1: When retry_after is in future, clicking re-evaluate schedules the retry without calling gateway."""
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]
    cust = Customer(external_customer_id=f"cust_t1_{uid}", name=f"Cust {uid}", email=f"cust_t1_{uid}@example.com")
    db.add(cust)
    db.commit()

    pay = Payment(customer_id=cust.id, gateway_payment_id=f"pay_live_t1_{uid}", amount=250.0, status="FAILED", failure_reason="NETWORK_TIMEOUT")
    db.add(pay)
    db.commit()

    future_retry = datetime.now(timezone.utc) + timedelta(minutes=8)
    case = RecoveryCase(
        customer_id=cust.id,
        payment_id=pay.id,
        revenue_at_risk=250.0,
        status="RE_EVALUATING",
        next_action="RETRY",
        recommended_action="RETRY",
        retry_count=1,
        retry_after=future_retry,
        priority_score=70.0,
        recovery_probability=0.70,
        root_cause="TRANSIENT_FAILURE"
    )
    db.add(case)
    db.commit()
    case_id = case.id
    db.close()

    with patch("app.services.gateway_simulator.SimulatedPaymentGateway.process_retry") as mock_retry:
        res = client.post(f"/api/recovery-cases/{case_id}/re-evaluate")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "SCHEDULED"
        assert "Retry scheduled" in data["message"]
        # Gateway was NEVER called
        assert mock_retry.call_count == 0

    db = SessionLocal()
    updated_case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    pay_db = db.query(Payment).filter(Payment.id == updated_case.payment_id).first()
    runs = db.query(AgentRun).filter(AgentRun.case_id == case_id).all()
    
    assert updated_case.status == "RE_EVALUATING"
    assert pay_db.status == "FAILED"
    # No execution run was created during early scheduling
    assert len(runs) == 0
    db.close()


def test_2_scheduler_does_not_execute_early():
    """Test 2 & 3: Scheduler ignores cases whose retry_after is still in the future."""
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]
    cust = Customer(external_customer_id=f"cust_t2_{uid}", name=f"Cust {uid}", email=f"cust_t2_{uid}@example.com")
    db.add(cust)
    db.commit()

    pay = Payment(customer_id=cust.id, gateway_payment_id=f"pay_live_t2_{uid}", amount=180.0, status="FAILED", failure_reason="NETWORK_TIMEOUT")
    db.add(pay)
    db.commit()

    future_retry = datetime.now(timezone.utc) + timedelta(minutes=15)
    case = RecoveryCase(
        customer_id=cust.id,
        payment_id=pay.id,
        revenue_at_risk=180.0,
        status="RE_EVALUATING",
        next_action="RETRY",
        recommended_action="RETRY",
        retry_count=1,
        retry_after=future_retry,
        priority_score=60.0
    )
    db.add(case)
    db.commit()
    case_id = case.id

    with patch("app.services.gateway_simulator.SimulatedPaymentGateway.process_retry") as mock_retry:
        res = scheduler_service.process_customer_action_lifecycle(db)
        assert mock_retry.call_count == 0

    db.refresh(case)
    assert case.status == "RE_EVALUATING"
    db.close()


def test_3_scheduler_executes_when_retry_after_reached():
    """Test 2 & 6: When retry_after <= now, scheduler runs re-evaluation and captures successful payment."""
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]
    cust = Customer(external_customer_id=f"cust_t3_{uid}", name=f"Cust {uid}", email=f"cust_t3_{uid}@example.com")
    db.add(cust)
    db.commit()

    pay = Payment(customer_id=cust.id, gateway_payment_id=f"pay_live_t3_{uid}", amount=300.0, status="FAILED", failure_reason="NETWORK_TIMEOUT")
    db.add(pay)
    db.commit()

    past_retry = datetime.now(timezone.utc) - timedelta(minutes=1)
    case = RecoveryCase(
        customer_id=cust.id,
        payment_id=pay.id,
        revenue_at_risk=300.0,
        status="RE_EVALUATING",
        next_action="RETRY",
        recommended_action="RETRY",
        retry_count=1,
        retry_after=past_retry,
        priority_score=80.0
    )
    db.add(case)
    db.commit()
    case_id = case.id

    with patch("app.services.gateway_simulator.SimulatedPaymentGateway.process_retry") as mock_retry:
        mock_retry.return_value = {
            "status": "SUCCESS",
            "transaction_id": f"txn_succ_t3_{uid}",
            "amount_recovered": 300.0,
            "gateway_code": "200_OK",
            "message": "Payment captured successfully."
        }
        res = scheduler_service.process_customer_action_lifecycle(db)
        assert res["reevaluated_cases"] >= 1
        assert mock_retry.call_count == 1

    db.refresh(case)
    db.refresh(pay)
    assert case.status == "RECOVERED"
    assert case.next_action == "NONE"
    assert pay.status == "SUCCESS"
    db.close()


def test_4_duplicate_clicks_before_due_do_not_create_duplicate_runs(client):
    """Test 4: Multiple clicks while waiting schedule idempotently with 0 gateway calls."""
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]
    cust = Customer(external_customer_id=f"cust_t4_{uid}", name=f"Cust {uid}", email=f"cust_t4_{uid}@example.com")
    db.add(cust)
    db.commit()

    pay = Payment(customer_id=cust.id, gateway_payment_id=f"pay_live_t4_{uid}", amount=200.0, status="FAILED", failure_reason="NETWORK_TIMEOUT")
    db.add(pay)
    db.commit()

    future_retry = datetime.now(timezone.utc) + timedelta(minutes=10)
    case = RecoveryCase(
        customer_id=cust.id,
        payment_id=pay.id,
        revenue_at_risk=200.0,
        status="RE_EVALUATING",
        next_action="RETRY",
        recommended_action="RETRY",
        retry_count=1,
        retry_after=future_retry
    )
    db.add(case)
    db.commit()
    case_id = case.id
    db.close()

    with patch("app.services.gateway_simulator.SimulatedPaymentGateway.process_retry") as mock_retry:
        # Click 1
        res1 = client.post(f"/api/recovery-cases/{case_id}/re-evaluate")
        assert res1.status_code == 200
        assert res1.json()["status"] == "SCHEDULED"

        # Click 2
        res2 = client.post(f"/api/recovery-cases/{case_id}/re-evaluate")
        assert res2.status_code == 200
        assert res2.json()["status"] == "SCHEDULED"

        # Click 3
        res3 = client.post(f"/api/recovery-cases/{case_id}/re-evaluate")
        assert res3.status_code == 200
        assert res3.json()["status"] == "SCHEDULED"

        assert mock_retry.call_count == 0

    db = SessionLocal()
    runs = db.query(AgentRun).filter(AgentRun.case_id == case_id).all()
    assert len(runs) == 0
    db.close()


def test_5_payment_succeeds_externally_while_waiting_cancels_retry():
    """Test 5: If payment becomes SUCCESS externally while waiting, scheduler marks case RECOVERED without retrying."""
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]
    cust = Customer(external_customer_id=f"cust_t5_{uid}", name=f"Cust {uid}", email=f"cust_t5_{uid}@example.com")
    db.add(cust)
    db.commit()

    # External success occurred
    pay = Payment(customer_id=cust.id, gateway_payment_id=f"pay_live_t5_{uid}", amount=450.0, status="SUCCESS", failure_reason=None)
    db.add(pay)
    db.commit()

    past_retry = datetime.now(timezone.utc) - timedelta(minutes=5)
    case = RecoveryCase(
        customer_id=cust.id,
        payment_id=pay.id,
        revenue_at_risk=450.0,
        status="RE_EVALUATING",
        next_action="RETRY",
        retry_after=past_retry
    )
    db.add(case)
    db.commit()
    case_id = case.id

    with patch("app.services.gateway_simulator.SimulatedPaymentGateway.process_retry") as mock_retry:
        res = scheduler_service.process_customer_action_lifecycle(db)
        assert mock_retry.call_count == 0

    db.refresh(case)
    assert case.status == "RECOVERED"
    assert case.next_action == "NONE"
    db.close()


def test_6_guardrail_blocks_retry_at_execution_time_if_condition_changed():
    """Test 8: If customer opts out while case was waiting, scheduler re-evaluates guardrails and stops recovery."""
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]
    # Customer opts out before retry execution
    cust = Customer(external_customer_id=f"cust_t6_{uid}", name=f"Cust {uid}", email=f"cust_t6_{uid}@example.com", opted_out=True)
    db.add(cust)
    db.commit()

    pay = Payment(customer_id=cust.id, gateway_payment_id=f"pay_live_t6_{uid}", amount=100.0, status="FAILED", failure_reason="NETWORK_TIMEOUT")
    db.add(pay)
    db.commit()

    past_retry = datetime.now(timezone.utc) - timedelta(minutes=2)
    case = RecoveryCase(
        customer_id=cust.id,
        payment_id=pay.id,
        revenue_at_risk=100.0,
        status="RE_EVALUATING",
        next_action="RETRY",
        recommended_action="RETRY",
        retry_count=1,
        retry_after=past_retry
    )
    db.add(case)
    db.commit()
    case_id = case.id

    with patch("app.services.gateway_simulator.SimulatedPaymentGateway.process_retry") as mock_retry:
        scheduler_service.process_customer_action_lifecycle(db)
        # Opt-out guardrail blocked retry execution
        assert mock_retry.call_count == 0

    db.refresh(case)
    assert case.status == "STOPPED"
    db.close()
