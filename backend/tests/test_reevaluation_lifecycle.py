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


def test_1_network_timeout_reevaluation_lifecycle(client):
    """Scenario 1:
    - Initial retry fails -> enters RE_EVALUATING
    - Trigger re-evaluation -> creates SECOND AgentRun and re-executes decision workflow
    """
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]
    customer = Customer(external_customer_id=f"cust_{uid}", name=f"Test Cust {uid}", email=f"cust_{uid}@example.com", lifetime_value=1200.0)
    db.add(customer)
    db.commit()

    payment = Payment(customer_id=customer.id, gateway_payment_id=f"pay_live_{uid}", amount=350.0, status="FAILED", failure_reason="NETWORK_TIMEOUT")
    db.add(payment)
    db.commit()

    case = RecoveryCase(
        customer_id=customer.id,
        payment_id=payment.id,
        revenue_at_risk=350.0,
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

    # Step 1: Execute initial retry -> simulated failure
    with patch("app.services.gateway_simulator.SimulatedPaymentGateway.process_retry") as mock_retry:
        mock_retry.return_value = {
            "status": "FAILED",
            "transaction_id": f"txn_fail_{uid}",
            "amount_recovered": 0.0,
            "gateway_code": "DECLINED",
            "message": "Payment retry failed: NETWORK_TIMEOUT"
        }
        res1 = client.post(f"/api/recovery-cases/{case_id}/approve", json={"action": "RETRY"})
        assert res1.status_code == 200

    db = SessionLocal()
    case1 = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    pay1 = db.query(Payment).filter(Payment.id == case1.payment_id).first()
    runs1 = db.query(AgentRun).filter(AgentRun.case_id == case_id).all()
    assert case1.status == "RE_EVALUATING"
    assert case1.retry_count == 1
    assert pay1.status == "FAILED"
    assert len(runs1) == 1
    assert runs1[0].status == "COMPLETED"
    assert runs1[0].final_result == "RETRY_FAILED"
    db.close()

    # Step 2: Trigger re-evaluation when due (advance retry_after)
    db = SessionLocal()
    case_db = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    case_db.retry_after = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()
    db.close()

    with patch("app.services.gateway_simulator.SimulatedPaymentGateway.process_retry") as mock_retry:
        mock_retry.return_value = {
            "status": "SUCCESS",
            "transaction_id": f"txn_succ_{uid}",
            "amount_recovered": 350.0,
            "gateway_code": "200_OK",
            "message": "Payment captured successfully."
        }
        res2 = client.post(f"/api/recovery-cases/{case_id}/re-evaluate")
        assert res2.status_code == 200

    db = SessionLocal()
    case2 = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()

    pay2 = db.query(Payment).filter(Payment.id == case2.payment_id).first()
    runs2 = db.query(AgentRun).filter(AgentRun.case_id == case_id).order_by(AgentRun.started_at.asc()).all()
    
    # Second AgentRun was created and executed
    assert len(runs2) == 2
    assert runs2[1].status == "COMPLETED"
    assert pay2.status == "SUCCESS"
    assert case2.status == "RECOVERED"
    assert case2.next_action == "NONE"
    db.close()


def test_2_network_retry_max_retries_reaches_stopped(client):
    """Scenario 2: Retrying until max attempts (3) terminates cleanly in STOPPED."""
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]
    customer = Customer(external_customer_id=f"cust_{uid}", name=f"Test Cust {uid}", email=f"cust_{uid}@example.com", lifetime_value=900.0)
    db.add(customer)
    db.commit()

    payment = Payment(customer_id=customer.id, gateway_payment_id=f"pay_live_{uid}", amount=120.0, status="FAILED", failure_reason="NETWORK_TIMEOUT")
    db.add(payment)
    db.commit()

    case = RecoveryCase(
        customer_id=customer.id,
        payment_id=payment.id,
        revenue_at_risk=120.0,
        status="RE_EVALUATING",
        next_action="RE_EVALUATE",
        recommended_action="RETRY",
        retry_count=2, # Currently on attempt 2, next attempt will be #3 (max)
        priority_score=60.0,
        recovery_probability=0.60,
        root_cause="TRANSIENT_FAILURE"
    )
    db.add(case)
    db.commit()
    case_id = case.id
    db.close()

    # Trigger re-evaluation with simulated failure
    with patch("app.services.gateway_simulator.SimulatedPaymentGateway.process_retry") as mock_retry:
        mock_retry.return_value = {
            "status": "FAILED",
            "transaction_id": f"txn_fail3_{uid}",
            "amount_recovered": 0.0,
            "gateway_code": "DECLINED",
            "message": "Payment retry failed: NETWORK_TIMEOUT"
        }
        res = client.post(f"/api/recovery-cases/{case_id}/re-evaluate")
        assert res.status_code == 200

    db = SessionLocal()
    updated_case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    assert updated_case.status == "STOPPED"
    assert updated_case.retry_count == 3
    assert updated_case.next_action == "NONE"
    db.close()


def test_3_scheduler_processes_reevaluation_when_due():
    """Scenario 3: Scheduler automatically picks up due RE_EVALUATING cases."""
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]
    customer = Customer(external_customer_id=f"cust_{uid}", name=f"Test Cust {uid}", email=f"cust_{uid}@example.com", lifetime_value=2000.0)
    db.add(customer)
    db.commit()

    payment = Payment(customer_id=customer.id, gateway_payment_id=f"pay_sched_{uid}", amount=500.0, status="FAILED", failure_reason="NETWORK_TIMEOUT")
    db.add(payment)
    db.commit()

    past_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    case = RecoveryCase(
        customer_id=customer.id,
        payment_id=payment.id,
        revenue_at_risk=500.0,
        status="RE_EVALUATING",
        next_action="RE_EVALUATE",
        recommended_action="RETRY",
        retry_count=1,
        retry_after=past_time, # Due for re-evaluation
        priority_score=75.0,
        recovery_probability=0.75,
        root_cause="TRANSIENT_FAILURE"
    )
    db.add(case)
    db.commit()
    case_id = case.id

    # Run scheduler process
    with patch("app.services.gateway_simulator.SimulatedPaymentGateway.process_retry") as mock_retry:
        mock_retry.return_value = {
            "status": "SUCCESS",
            "transaction_id": f"txn_succ_sched_{uid}",
            "amount_recovered": 500.0,
            "gateway_code": "200_OK",
            "message": "Payment captured successfully."
        }
        res_sched = scheduler_service.process_customer_action_lifecycle(db)
        assert res_sched["reevaluated_cases"] >= 1

    db.refresh(case)
    db.refresh(payment)
    assert case.status == "RECOVERED"
    assert case.next_action == "NONE"
    assert payment.status == "SUCCESS"
    db.close()


def test_4_idempotent_duplicate_protection_during_reevaluation(client):
    """Scenario 4: If a case is already RECOVERED or execution is in progress, re-evaluation is idempotent and protected."""
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]
    customer = Customer(external_customer_id=f"cust_{uid}", name=f"Test Cust {uid}", email=f"cust_{uid}@example.com", lifetime_value=1000.0)
    db.add(customer)
    db.commit()

    payment = Payment(customer_id=customer.id, gateway_payment_id=f"pay_rec_{uid}", amount=200.0, status="SUCCESS", failure_reason=None)
    db.add(payment)
    db.commit()

    case = RecoveryCase(
        customer_id=customer.id,
        payment_id=payment.id,
        revenue_at_risk=200.0,
        status="RECOVERED",
        next_action="NONE",
        recommended_action="RETRY",
        priority_score=0.0
    )
    db.add(case)
    db.commit()
    case_id = case.id
    db.close()

    # Calling re-evaluate on a recovered case must be rejected with 400
    res = client.post(f"/api/recovery-cases/{case_id}/re-evaluate")
    assert res.status_code == 400
    assert "already resolved as RECOVERED" in res.json()["detail"]
