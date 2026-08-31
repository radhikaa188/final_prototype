import pytest
import uuid
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.db.models import Customer, Payment, RecoveryCase, AgentRun, RecoveryAction, AuditEvent, User
from app.services.gateway_simulator import gateway_simulator
from app.auth.security import create_access_token
from app.auth.init_users import seed_default_users

@pytest.fixture
def client(db: Session):
    seed_default_users(db)
    ops_user = db.query(User).filter(User.role == "OPS").first()
    token = create_access_token({"sub": ops_user.id, "email": ops_user.email, "role": ops_user.role})
    tc = TestClient(app)
    tc.headers["Authorization"] = f"Bearer {token}"
    return tc

def test_scenario_1_approve_retry_success(db: Session, client: TestClient):
    """Test 1: Approve RETRY + Success workflow execution."""
    uid = uuid.uuid4().hex[:8]
    cust = Customer(external_customer_id=f"ext_c1_{uid}", name="Test Customer 1", email=f"cust1_{uid}@example.com", opted_out=False)
    db.add(cust)
    db.commit()

    # Prefix with 'pay_test' to force gateway success simulator
    pay = Payment(customer_id=cust.id, gateway_payment_id=f"pay_test_s1_{uid}", amount=250.0, status="FAILED", failure_reason="GENERIC_DECLINE")
    db.add(pay)
    db.commit()

    case = RecoveryCase(
        payment_id=pay.id,
        customer_id=cust.id,
        status="ESCALATED",
        revenue_at_risk=250.0,
        recommended_action="HUMAN_REVIEW",
        next_action="HUMAN_REVIEW"
    )
    db.add(case)
    db.commit()

    # Employee approves RETRY
    response = client.post(f"/api/recovery-cases/{case.id}/approve", json={"action": "RETRY"})
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["run_status"] == "COMPLETED"
    assert res_data["final_result"] == "RECOVERED"
    assert res_data["case_status"] == "RECOVERED"
    assert res_data["payment_status"] == "SUCCESS"
    assert res_data["approved_action"] == "RETRY"
    assert res_data["amount_recovered"] == 250.0

    db.refresh(case)
    db.refresh(pay)
    assert pay.status == "SUCCESS"
    assert case.status == "RECOVERED"
    assert case.next_action == "NONE"

    # Verify timeline events
    events = db.query(AuditEvent).filter(AuditEvent.case_id == case.id).order_by(AuditEvent.created_at.asc()).all()
    event_types = [e.event_type for e in events]
    assert "HUMAN_APPROVAL" in event_types
    assert "POLICY_GUARDRAILS_VALIDATED" in event_types
    assert "RECOVERY_ACTION_EXECUTED" in event_types
    assert "PAYMENT_RESULT_RECEIVED" in event_types
    assert "RECOVERED" in event_types

def test_scenario_2_approve_retry_failed_gateway(db: Session, client: TestClient):
    """Test 2: Approve RETRY + Failed Gateway retry attempt."""
    # Temporarily force simulator failure
    old_rate = gateway_simulator.force_success_rate
    gateway_simulator.force_success_rate = 0.0
    try:
        uid = uuid.uuid4().hex[:8]
        cust = Customer(external_customer_id=f"ext_c2_{uid}", name="Test Customer 2", email=f"cust2_{uid}@example.com", opted_out=False)
        db.add(cust)
        db.commit()

        pay = Payment(customer_id=cust.id, gateway_payment_id=f"pay_fail_s2_{uid}", amount=150.0, status="FAILED", failure_reason="GENERIC_DECLINE")
        db.add(pay)
        db.commit()

        case = RecoveryCase(
            payment_id=pay.id,
            customer_id=cust.id,
            status="ESCALATED",
            revenue_at_risk=150.0,
            recommended_action="HUMAN_REVIEW",
            next_action="HUMAN_REVIEW"
        )
        db.add(case)
        db.commit()

        # Employee approves RETRY
        response = client.post(f"/api/recovery-cases/{case.id}/approve", json={"action": "RETRY"})
        assert response.status_code == 200
        res_data = response.json()
        assert res_data["run_status"] == "COMPLETED"
        assert res_data["final_result"] in ("FAILED", "RETRY_FAILED")
        assert res_data["case_status"] == "RE_EVALUATING"
        assert res_data["payment_status"] == "FAILED"

        db.refresh(case)
        db.refresh(pay)
        assert pay.status == "FAILED"
        assert case.status == "RE_EVALUATING"
    finally:
        gateway_simulator.force_success_rate = old_rate

def test_scenario_3_approve_guardrail_block(db: Session, client: TestClient):
    """Test 3: Approve + Guardrail Block (Customer Opted Out)."""
    uid = uuid.uuid4().hex[:8]
    cust = Customer(external_customer_id=f"ext_c3_{uid}", name="Test Customer 3", email=f"cust3_{uid}@example.com", opted_out=True)
    db.add(cust)
    db.commit()

    pay = Payment(customer_id=cust.id, gateway_payment_id=f"pay_test_s3_{uid}", amount=90.0, status="FAILED", failure_reason="GENERIC_DECLINE")
    db.add(pay)
    db.commit()

    case = RecoveryCase(
        payment_id=pay.id,
        customer_id=cust.id,
        status="ESCALATED",
        revenue_at_risk=90.0,
        recommended_action="HUMAN_REVIEW",
        next_action="HUMAN_REVIEW"
    )
    db.add(case)
    db.commit()

    # Employee approves RETRY
    response = client.post(f"/api/recovery-cases/{case.id}/approve", json={"action": "RETRY"})
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["run_status"] == "BLOCKED"
    assert res_data["case_status"] == "STOPPED"
    assert res_data["payment_status"] == "FAILED"

    db.refresh(case)
    db.refresh(pay)
    assert pay.status == "FAILED"
    assert case.status == "STOPPED"

    # Verify no gateway actions executed
    actions = db.query(RecoveryAction).filter(RecoveryAction.case_id == case.id).all()
    assert len(actions) == 0

def test_scenario_4_human_reject(db: Session, client: TestClient):
    """Test 4: Human Reject case scenario."""
    uid = uuid.uuid4().hex[:8]
    cust = Customer(external_customer_id=f"ext_c4_{uid}", name="Test Customer 4", email=f"cust4_{uid}@example.com", opted_out=False)
    db.add(cust)
    db.commit()

    pay = Payment(customer_id=cust.id, gateway_payment_id=f"pay_test_s4_{uid}", amount=120.0, status="FAILED", failure_reason="GENERIC_DECLINE")
    db.add(pay)
    db.commit()

    case = RecoveryCase(
        payment_id=pay.id,
        customer_id=cust.id,
        status="ESCALATED",
        revenue_at_risk=120.0,
        recommended_action="HUMAN_REVIEW",
        next_action="HUMAN_REVIEW"
    )
    db.add(case)
    db.commit()

    # Employee rejects case
    response = client.post(f"/api/recovery-cases/{case.id}/reject")
    assert response.status_code == 200
    assert response.json()["status"] == "STOPPED"

    db.refresh(case)
    assert case.status == "STOPPED"
    assert case.next_action == "NONE"

    # Verify rejection audit event exists
    events = db.query(AuditEvent).filter(AuditEvent.case_id == case.id, AuditEvent.event_type == "HUMAN_REJECTION").all()
    assert len(events) == 1

def test_scenario_5_already_recovered(db: Session, client: TestClient):
    """Test 5: Try to approve a case that is already RECOVERED."""
    uid = uuid.uuid4().hex[:8]
    cust = Customer(external_customer_id=f"ext_c5_{uid}", name="Test Customer 5", email=f"cust5_{uid}@example.com", opted_out=False)
    db.add(cust)
    db.commit()

    pay = Payment(customer_id=cust.id, gateway_payment_id=f"pay_test_s5_{uid}", amount=180.0, status="SUCCESS")
    db.add(pay)
    db.commit()

    case = RecoveryCase(
        payment_id=pay.id,
        customer_id=cust.id,
        status="RECOVERED",
        revenue_at_risk=180.0,
        recommended_action="NONE",
        next_action="NONE"
    )
    db.add(case)
    db.commit()

    # Attempt to approve already recovered case
    response = client.post(f"/api/recovery-cases/{case.id}/approve", json={"action": "RETRY"})
    assert response.status_code == 400
    assert "already resolved as RECOVERED" in response.json()["detail"]

def test_scenario_6_no_replacing_human_choice(db: Session, client: TestClient):
    """Test 6: Verify the MANUAL_APPROVE flow preserves the human action choice, bypassing ML recommendation re-selection."""
    uid = uuid.uuid4().hex[:8]
    cust = Customer(external_customer_id=f"ext_c6_{uid}", name="Test Customer 6", email=f"cust6_{uid}@example.com", opted_out=False)
    db.add(cust)
    db.commit()

    pay = Payment(customer_id=cust.id, gateway_payment_id=f"pay_test_s6_{uid}", amount=450.0, status="FAILED", failure_reason="GENERIC_DECLINE")
    db.add(pay)
    db.commit()

    case = RecoveryCase(
        payment_id=pay.id,
        customer_id=cust.id,
        status="ESCALATED",
        revenue_at_risk=450.0,
        recommended_action="CUSTOMER_NUDGE",
        next_action="HUMAN_REVIEW"
    )
    db.add(case)
    db.commit()

    # ML recommended action on case is CUSTOMER_NUDGE, but human approves RETRY
    response = client.post(f"/api/recovery-cases/{case.id}/approve", json={"action": "RETRY"})
    assert response.status_code == 200
    assert response.json()["approved_action"] == "RETRY"

    db.refresh(case)
    db.refresh(pay)
    assert pay.status == "SUCCESS"
    assert case.status == "RECOVERED"
    # The actual successful action should update recommended_action on the case to RETRY
    assert case.recommended_action == "RETRY"

def test_scenario_7_database_and_dashboard(db: Session, client: TestClient):
    """Test 7: Verify database state transitions and dashboard metrics increase from persisted values."""
    # Fetch initial dashboard summary
    initial_summary = client.get("/api/dashboard/summary").json()
    initial_recovered = initial_summary["revenue_recovered"]

    uid = uuid.uuid4().hex[:8]
    cust = Customer(external_customer_id=f"ext_c7_{uid}", name="Test Customer 7", email=f"cust7_{uid}@example.com", opted_out=False)
    db.add(cust)
    db.commit()

    pay = Payment(customer_id=cust.id, gateway_payment_id=f"pay_test_s7_{uid}", amount=320.0, status="FAILED", failure_reason="GENERIC_DECLINE")
    db.add(pay)
    db.commit()

    case = RecoveryCase(
        payment_id=pay.id,
        customer_id=cust.id,
        status="ESCALATED",
        revenue_at_risk=320.0,
        recommended_action="HUMAN_REVIEW",
        next_action="HUMAN_REVIEW"
    )
    db.add(case)
    db.commit()

    # Approve RETRY
    response = client.post(f"/api/recovery-cases/{case.id}/approve", json={"action": "RETRY"})
    assert response.status_code == 200

    # Refresh DB objects
    db.refresh(case)
    db.refresh(pay)
    assert pay.status == "SUCCESS"
    assert case.status == "RECOVERED"
    
    # Check that RecoveryAction status is SUCCESS
    action = db.query(RecoveryAction).filter(RecoveryAction.case_id == case.id).first()
    assert action is not None
    assert action.status == "SUCCESS"
    assert action.amount_recovered == 320.0

    # Fetch updated dashboard summary and assert metrics increase
    updated_summary = client.get("/api/dashboard/summary").json()
    assert updated_summary["revenue_recovered"] == initial_recovered + 320.0

def test_scenario_8_approve_nudge_success(db: Session, client: TestClient):
    """Test 8: Approve CUSTOMER_NUDGE + Success workflow execution."""
    uid = uuid.uuid4().hex[:8]
    cust = Customer(external_customer_id=f"ext_c8_{uid}", name="Test Customer 8", email=f"cust8_{uid}@example.com", opted_out=False)
    db.add(cust)
    db.commit()

    # Prefix with 'pay_test' to force gateway success simulator
    pay = Payment(customer_id=cust.id, gateway_payment_id=f"pay_test_s8_{uid}", amount=190.0, status="FAILED", failure_reason="GENERIC_DECLINE")
    db.add(pay)
    db.commit()

    case = RecoveryCase(
        payment_id=pay.id,
        customer_id=cust.id,
        status="ESCALATED",
        revenue_at_risk=190.0,
        recommended_action="HUMAN_REVIEW",
        next_action="HUMAN_REVIEW"
    )
    db.add(case)
    db.commit()

    # Employee approves CUSTOMER_NUDGE
    response = client.post(f"/api/recovery-cases/{case.id}/approve", json={"action": "CUSTOMER_NUDGE"})
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["run_status"] == "COMPLETED"
    assert res_data["final_result"] == "RECOVERED"
    assert res_data["case_status"] == "RECOVERED"
    assert res_data["payment_status"] == "SUCCESS"
    assert res_data["approved_action"] == "CUSTOMER_NUDGE"
    assert res_data["amount_recovered"] == 190.0

    db.refresh(case)
    db.refresh(pay)
    assert pay.status == "SUCCESS"
    assert case.status == "RECOVERED"
    assert case.recommended_action == "CUSTOMER_NUDGE"

    # Verify corresponding RecoveryAction
    action = db.query(RecoveryAction).filter(RecoveryAction.case_id == case.id).first()
    assert action is not None
    assert action.action_type == "CUSTOMER_NUDGE"
    assert action.status == "SUCCESS"
    assert action.amount_recovered == 190.0

