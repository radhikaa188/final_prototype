import pytest
import uuid
import json
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.db.models import Customer, Payment, RecoveryCase, AgentRun, AgentRunStep, RecoveryAction, AuditEvent, Notification, User
from app.auth.security import create_access_token
from app.auth.init_users import seed_default_users

from app.main import app

@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

from app.services.execution_service import execution_service

@pytest.fixture
def client(db: Session):
    seed_default_users(db)
    ops_user = db.query(User).filter(User.role == "OPS").first()
    token = create_access_token({"sub": ops_user.id, "email": ops_user.email, "role": ops_user.role})
    tc = TestClient(app)
    tc.headers["Authorization"] = f"Bearer {token}"
    return tc

def test_scenario_a_automatic_recovery_timestamps(db: Session, client: TestClient):
    """Test A: Automatic recovery timestamp aware and chronological progression."""
    uid = uuid.uuid4().hex[:8]
    cust = Customer(
        external_customer_id=f"ext_ta_{uid}",
        name="Test A Customer",
        email=f"ta_{uid}@example.com",
        opted_out=False
    )
    db.add(cust)
    db.commit()

    # Trigger webhook to start automatic recovery workflow
    # prefix 'pay_test' triggers gateway success
    gateway_payment_id = f"pay_test_ta_{uid}"
    payload = {
        "event": "payment.failed",
        "event_id": f"evt_ta_{uid}",
        "payload": {
            "payment": {
                "id": gateway_payment_id,
                "amount": 12000,
                "status": "failed",
                "error_code": "GATEWAY_ERROR",
                "error_description": "Gateway error",
                "customer": {
                    "id": cust.external_customer_id
                }
            }
        }
    }
    
    # 1. Capture webhook ingestion timestamp
    t_start = datetime.now(timezone.utc)
    response = client.post("/api/webhooks/razorpay", json=payload)
    assert response.status_code == 200
    t_end = datetime.now(timezone.utc)
    
    db.rollback()
    db.expire_all()

    # 2. Query created entities and verify timestamps
    pay = db.query(Payment).filter(Payment.gateway_payment_id == gateway_payment_id).first()
    assert pay is not None
    case = db.query(RecoveryCase).filter(RecoveryCase.payment_id == pay.id).first()
    assert case is not None
    
    # Trigger execution workflow
    run = AgentRun(case_id=case.id, trigger_type="AUTOMATIC", status="PENDING")
    db.add(run)
    db.commit()
    
    execution_service.run_agent_workflow_sync(run.id)
    db.expire_all()
    db.refresh(case)
    
    assert case.status == "RECOVERED"
    
    # Assert created_at and closed_at are chronological
    assert case.created_at is not None
    assert case.closed_at is not None
    assert case.closed_at >= case.created_at

    # Audit events chronological progression
    events = db.query(AuditEvent).filter(AuditEvent.case_id == case.id).order_by(AuditEvent.created_at.asc()).all()
    assert len(events) >= 5
    
    prev_time = None
    for evt in events:
        evt_time = evt.created_at.replace(tzinfo=timezone.utc) if evt.created_at.tzinfo is None else evt.created_at
        if prev_time:
            assert evt_time >= prev_time
        prev_time = evt_time

def test_scenario_b_customer_action_timestamps(db: Session, client: TestClient):
    """Test B: Customer action workflow timestamps progression."""
    uid = uuid.uuid4().hex[:8]
    cust = Customer(
        external_customer_id=f"ext_tb_{uid}",
        name="Test B Customer",
        email=f"tb_{uid}@example.com",
        opted_out=False
    )
    db.add(cust)
    db.commit()

    # Trigger automatic run which should result in CUSTOMER_ACTION_REQUIRED
    # We will trigger webhook
    # Prefix with 'pay_fail' to force gateway failure and classification as customer action required
    gateway_payment_id = f"pay_fail_tb_{uid}"
    payload = {
        "event": "payment.failed",
        "event_id": f"evt_tb_{uid}",
        "payload": {
            "payment": {
                "id": gateway_payment_id,
                "amount": 15000,
                "status": "failed",
                "error_code": "INSUFFICIENT_FUNDS",
                "error_description": "Failed due to insufficient funds",
                "customer": {
                    "id": cust.external_customer_id
                }
            }
        }
    }
    
    response = client.post("/api/webhooks/razorpay", json=payload)
    assert response.status_code == 200
    db.expire_all()

    db.rollback()
    db.expire_all()

    pay = db.query(Payment).filter(Payment.gateway_payment_id == gateway_payment_id).first()
    assert pay is not None
    case = db.query(RecoveryCase).filter(RecoveryCase.payment_id == pay.id).first()
    assert case is not None
    
    # Trigger execution workflow to run ML diagnosis and reach CUSTOMER_ACTION_REQUIRED state
    run = AgentRun(case_id=case.id, trigger_type="AUTOMATIC", status="PENDING")
    db.add(run)
    db.commit()
    
    execution_service.run_agent_workflow_sync(run.id)
    db.rollback()
    db.expire_all()
    db.refresh(case)
    
    assert case.status == "CUSTOMER_ACTION_REQUIRED"
    assert case.customer_action_required is True

    # Capture customer lifecycle timestamps
    w_since = case.waiting_since.replace(tzinfo=timezone.utc) if case.waiting_since.tzinfo is None else case.waiting_since
    r_after = case.retry_after.replace(tzinfo=timezone.utc) if case.retry_after.tzinfo is None else case.retry_after
    exp_at = case.expires_at.replace(tzinfo=timezone.utc) if case.expires_at.tzinfo is None else case.expires_at

    # Assert correct time sequence bounds
    assert w_since <= r_after
    assert r_after <= exp_at

    # Resolve customer payment issue
    res = client.post(f"/api/recovery-cases/{case.id}/customer-action", json={})
    assert res.status_code == 200
    db.rollback()
    db.expire_all()
    db.refresh(case)
    assert case.customer_action_status == "COMPLETED"

    # Simulate fast-forwarding time to retry_after for manual re-evaluation
    # We will temporarily update case.retry_after to past UTC time to bypass api timing enforcement
    case.retry_after = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()

    # Now trigger re-evaluation
    # We will update payment gateway ID to 'pay_test' to force success on re-evaluation retry
    pay.gateway_payment_id = f"pay_test_tb_success_{uid}"
    db.commit()

    response = client.post(f"/api/recovery-cases/{case.id}/re-evaluate")
    assert response.status_code == 200

    db.rollback()
    db.expire_all()
    db.refresh(case)
    db.refresh(pay)
    assert case.status == "RECOVERED"
    assert pay.status == "SUCCESS"

    cl_at = case.closed_at.replace(tzinfo=timezone.utc) if case.closed_at.tzinfo is None else case.closed_at
    assert cl_at >= w_since

def test_scenario_c_human_review_timestamps(db: Session, client: TestClient):
    """Test C: Human review approved workflow timestamps sequence."""
    uid = uuid.uuid4().hex[:8]
    cust = Customer(
        external_customer_id=f"ext_tc_{uid}",
        name="Test C Customer",
        email=f"tc_{uid}@example.com",
        opted_out=False
    )
    db.add(cust)
    db.commit()

    # Trigger failed payment
    pay = Payment(
        customer_id=cust.id,
        gateway_payment_id=f"pay_test_tc_{uid}",
        amount=500.0,
        status="FAILED",
        failure_reason="GENERIC_DECLINE"
    )
    db.add(pay)
    db.commit()

    case = RecoveryCase(
        payment_id=pay.id,
        customer_id=cust.id,
        status="ESCALATED",
        revenue_at_risk=500.0,
        recommended_action="HUMAN_REVIEW",
        next_action="HUMAN_REVIEW"
    )
    db.add(case)
    db.commit()

    # Approve Retry
    t_approve = datetime.now(timezone.utc)
    response = client.post(f"/api/recovery-cases/{case.id}/approve", json={"action": "RETRY"})
    assert response.status_code == 200
    
    db.refresh(case)
    db.refresh(pay)
    assert case.status == "RECOVERED"
    assert pay.status == "SUCCESS"

    # Query chronological timeline events
    events = db.query(AuditEvent).filter(AuditEvent.case_id == case.id).order_by(AuditEvent.created_at.asc()).all()
    
    # Assert sequence of event descriptions
    event_types = [e.event_type for e in events]
    assert "HUMAN_APPROVAL" in event_types
    assert "RECOVERED" in event_types

    # Find run and verify steps sorting sequence
    run = db.query(AgentRun).filter(AgentRun.case_id == case.id).first()
    assert run is not None
    
    steps = db.query(AgentRunStep).filter(AgentRunStep.run_id == run.id).order_by(AgentRunStep.step_number.asc()).all()
    assert len(steps) > 0
    
    # Assert step_number is strictly increasing
    prev_step_num = 0
    for s in steps:
        assert s.step_number > prev_step_num
        prev_step_num = s.step_number
