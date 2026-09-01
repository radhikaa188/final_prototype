import pytest
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.db.models import Customer, Payment, RecoveryCase, AgentRun, RecoveryAction, AuditEvent, AgentRunStep, User
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


def test_1_transient_retry_lifecycle_correlation(client):
    """Scenario 1: Transient network failure lifecycle maintains stable Payment & Case IDs."""
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]
    cust = Customer(external_customer_id=f"cust_corr_{uid}", name=f"Correlation Cust {uid}", email=f"corr_{uid}@example.com", lifetime_value=1500.0)
    db.add(cust)
    db.commit()
    customer_id = cust.id

    pay = Payment(customer_id=customer_id, gateway_payment_id=f"pay_corr_{uid}", amount=420.0, status="FAILED", failure_reason="NETWORK_TIMEOUT")
    db.add(pay)
    db.commit()
    payment_id = pay.id
    gateway_payment_id = pay.gateway_payment_id

    case = RecoveryCase(
        customer_id=customer_id,
        payment_id=payment_id,
        revenue_at_risk=420.0,
        status="PRIORITIZED",
        next_action="RETRY",
        recommended_action="RETRY",
        priority_score=85.0,
        recovery_probability=0.85,
        root_cause="TRANSIENT_FAILURE"
    )
    db.add(case)
    db.commit()
    case_id = case.id
    db.close()

    # Stage 1: Initial State Check
    db = SessionLocal()
    c1 = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    assert c1.id == case_id
    assert c1.payment_id == payment_id
    assert c1.customer_id == customer_id
    assert c1.status == "PRIORITIZED"
    db.close()

    # Stage 2: Initial Retry Execution (Fails)
    with patch("app.services.gateway_simulator.SimulatedPaymentGateway.process_retry") as mock_retry:
        mock_retry.return_value = {
            "status": "FAILED",
            "transaction_id": f"txn_fail1_{uid}",
            "amount_recovered": 0.0,
            "gateway_code": "DECLINED",
            "message": "Payment retry failed: NETWORK_TIMEOUT"
        }
        res = client.post(f"/api/recovery-cases/{case_id}/approve", json={"action": "RETRY"})
        assert res.status_code == 200

    db = SessionLocal()
    c2 = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    p2 = db.query(Payment).filter(Payment.id == payment_id).first()
    runs2 = db.query(AgentRun).filter(AgentRun.case_id == case_id).all()
    actions2 = db.query(RecoveryAction).filter(RecoveryAction.case_id == case_id).all()
    
    # Business IDs remain identical
    assert c2.id == case_id
    assert c2.payment_id == payment_id
    assert c2.customer_id == customer_id
    assert p2.id == payment_id
    assert p2.gateway_payment_id == gateway_payment_id
    assert c2.status == "RE_EVALUATING"
    assert c2.retry_count == 1
    assert len(runs2) == 1
    assert len(actions2) == 1
    run1_id = runs2[0].id
    action1_id = actions2[0].id

    # Stage 3: Advance retry_after and run re-evaluation (Succeeds)
    c2.retry_after = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()
    db.close()

    with patch("app.services.gateway_simulator.SimulatedPaymentGateway.process_retry") as mock_retry:
        mock_retry.return_value = {
            "status": "SUCCESS",
            "transaction_id": f"txn_succ2_{uid}",
            "amount_recovered": 420.0,
            "gateway_code": "200_OK",
            "message": "Payment captured successfully."
        }
        res_reeval = client.post(f"/api/recovery-cases/{case_id}/re-evaluate")
        assert res_reeval.status_code == 200

    db = SessionLocal()
    c3 = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    p3 = db.query(Payment).filter(Payment.id == payment_id).first()
    runs3 = db.query(AgentRun).filter(AgentRun.case_id == case_id).order_by(AgentRun.started_at.asc()).all()
    actions3 = db.query(RecoveryAction).filter(RecoveryAction.case_id == case_id).order_by(RecoveryAction.executed_at.asc()).all()


    # Invariant assertions: Business IDs unchanged
    assert c3.id == case_id
    assert c3.payment_id == payment_id
    assert c3.customer_id == customer_id
    assert p3.id == payment_id
    assert p3.gateway_payment_id == gateway_payment_id
    assert p3.status == "SUCCESS"
    assert c3.status == "RECOVERED"
    assert c3.next_action == "NONE"

    # Execution IDs: Distinct runs & actions created for distinct execution attempts
    assert len(runs3) == 2
    assert runs3[0].id == run1_id
    assert runs3[1].id != run1_id
    assert runs3[1].case_id == case_id

    assert len(actions3) == 2
    assert actions3[0].id == action1_id
    assert actions3[1].id != action1_id
    assert actions3[1].case_id == case_id
    assert actions3[1].status == "SUCCESS"

    db.close()


def test_2_customer_action_lifecycle_correlation(client):
    """Scenario 2: Customer Action required lifecycle maintains stable Payment & Case IDs."""
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]
    cust = Customer(external_customer_id=f"cust_ca_{uid}", name=f"Customer Action Cust {uid}", email=f"ca_{uid}@example.com")
    db.add(cust)
    db.commit()
    customer_id = cust.id

    pay = Payment(customer_id=customer_id, gateway_payment_id=f"pay_ca_{uid}", amount=199.0, status="FAILED", failure_reason="CARD_EXPIRED")
    db.add(pay)
    db.commit()
    payment_id = pay.id
    gateway_payment_id = pay.gateway_payment_id

    now = datetime.now(timezone.utc)
    case = RecoveryCase(
        customer_id=customer_id,
        payment_id=payment_id,
        revenue_at_risk=199.0,
        status="CUSTOMER_ACTION_REQUIRED",
        customer_action_required=True,
        customer_action_type="UPDATE_CARD",
        customer_action_status="PENDING",
        next_action="WAIT_FOR_CUSTOMER_ACTION",
        retry_after=now + timedelta(hours=24),
        expires_at=now + timedelta(hours=72)
    )
    db.add(case)
    db.commit()
    case_id = case.id
    db.close()

    # Step 1: Simulate Customer Action Resolved
    res1 = client.post(f"/api/recovery-cases/{case_id}/customer-action", json={"action_type": "UPDATE_CARD"})
    assert res1.status_code == 200

    db = SessionLocal()
    case_ca = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    assert case_ca.id == case_id
    assert case_ca.payment_id == payment_id
    assert case_ca.customer_id == customer_id
    assert case_ca.customer_action_status == "COMPLETED"

    # Fast forward retry_after to past to allow re-evaluation
    case_ca.retry_after = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()
    db.close()

    # Step 2: Trigger Re-evaluation & Retry
    with patch("app.services.gateway_simulator.SimulatedPaymentGateway.process_retry") as mock_retry:
        mock_retry.return_value = {
            "status": "SUCCESS",
            "transaction_id": f"txn_succ_ca_{uid}",
            "amount_recovered": 199.0,
            "gateway_code": "200_OK",
            "message": "Payment captured successfully."
        }
        res2 = client.post(f"/api/recovery-cases/{case_id}/re-evaluate")
        assert res2.status_code == 200

    db = SessionLocal()
    final_case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    final_pay = db.query(Payment).filter(Payment.id == payment_id).first()
    
    assert final_case.id == case_id
    assert final_case.payment_id == payment_id
    assert final_case.customer_id == customer_id
    assert final_pay.id == payment_id
    assert final_pay.gateway_payment_id == gateway_payment_id
    assert final_case.status == "RECOVERED"
    assert final_pay.status == "SUCCESS"
    db.close()


def test_3_human_review_lifecycle_correlation(client):
    """Scenario 3: Human Review Escalated lifecycle maintains stable Payment & Case IDs."""
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]
    cust = Customer(external_customer_id=f"cust_hr_{uid}", name=f"Human Review Cust {uid}", email=f"hr_{uid}@example.com")
    db.add(cust)
    db.commit()
    customer_id = cust.id

    pay = Payment(customer_id=customer_id, gateway_payment_id=f"pay_hr_{uid}", amount=850.0, status="FAILED", failure_reason="SUSPICIOUS_TRANSACTION")
    db.add(pay)
    db.commit()
    payment_id = pay.id
    gateway_payment_id = pay.gateway_payment_id

    case = RecoveryCase(
        customer_id=customer_id,
        payment_id=payment_id,
        revenue_at_risk=850.0,
        status="ESCALATED",
        next_action="HUMAN_REVIEW",
        recommended_action="HUMAN_REVIEW",
        priority_score=95.0
    )
    db.add(case)
    db.commit()
    case_id = case.id
    db.close()

    # Step: Human Operator Approves Retry
    with patch("app.services.gateway_simulator.SimulatedPaymentGateway.process_retry") as mock_retry:
        mock_retry.return_value = {
            "status": "SUCCESS",
            "transaction_id": f"txn_succ_hr_{uid}",
            "amount_recovered": 850.0,
            "gateway_code": "200_OK",
            "message": "Payment captured successfully."
        }
        res = client.post(f"/api/recovery-cases/{case_id}/approve", json={"action": "RETRY"})
        assert res.status_code == 200

    db = SessionLocal()
    final_case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    final_pay = db.query(Payment).filter(Payment.id == payment_id).first()

    assert final_case.id == case_id
    assert final_case.payment_id == payment_id
    assert final_case.customer_id == customer_id
    assert final_pay.id == payment_id
    assert final_pay.gateway_payment_id == gateway_payment_id
    assert final_case.status == "RECOVERED"
    assert final_pay.status == "SUCCESS"
    db.close()


def test_4_database_relationship_integrity(client):
    """Scenario 4: Validates zero orphaned records across AgentRun, AgentRunStep, RecoveryAction, AuditEvent."""
    db = SessionLocal()
    
    # Check RecoveryCase -> Payment integrity
    cases = db.query(RecoveryCase).all()
    for c in cases:
        p = db.query(Payment).filter(Payment.id == c.payment_id).first()
        assert p is not None, f"Orphaned RecoveryCase {c.id} with missing payment_id {c.payment_id}"
        assert c.customer_id is not None

    # Check AgentRun -> RecoveryCase integrity
    runs = db.query(AgentRun).all()
    for r in runs:
        c = db.query(RecoveryCase).filter(RecoveryCase.id == r.case_id).first()
        assert c is not None, f"Orphaned AgentRun {r.id} with missing case_id {r.case_id}"

    # Check AgentRunStep -> AgentRun integrity
    steps = db.query(AgentRunStep).all()
    for s in steps:
        r = db.query(AgentRun).filter(AgentRun.id == s.run_id).first()
        assert r is not None, f"Orphaned AgentRunStep {s.id} with missing run_id {s.run_id}"


    # Check RecoveryAction -> RecoveryCase integrity
    actions = db.query(RecoveryAction).all()
    for a in actions:
        c = db.query(RecoveryCase).filter(RecoveryCase.id == a.case_id).first()
        assert c is not None, f"Orphaned RecoveryAction {a.id} with missing case_id {a.case_id}"

    # Check AuditEvent -> RecoveryCase integrity
    audit_events = db.query(AuditEvent).filter(AuditEvent.case_id.isnot(None)).all()
    for ae in audit_events:
        c = db.query(RecoveryCase).filter(RecoveryCase.id == ae.case_id).first()
        assert c is not None, f"Orphaned AuditEvent {ae.id} with missing case_id {ae.case_id}"

    db.close()
