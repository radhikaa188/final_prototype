import pytest
import uuid
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.db.models import Customer, Payment, RecoveryCase, Notification, User, AgentRun
from app.auth.security import create_access_token
from app.auth.init_users import seed_default_users
from app.services.notification_service import notification_service
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


def test_1_customer_action_required_and_completed_notifications(client):
    """Test 1: CUSTOMER_ACTION_REQUIRED on creation, and CUSTOMER_ACTION_COMPLETED on resolution."""
    # Step 1: Ingest payment requiring customer action
    res_gen = client.post("/api/test-mode/generate-payment", json={
        "amount": 250.0,
        "failure_reason": "INSUFFICIENT_FUNDS"
    })
    assert res_gen.status_code == 200
    case_id = res_gen.json()["case_id"]

    # Verify CUSTOMER_ACTION_REQUIRED notification exists
    res_notif = client.get("/api/notifications")
    assert res_notif.status_code == 200
    notifs = res_notif.json()["notifications"]
    req_notif = next((n for n in notifs if n["case_id"] == case_id and n["type"] == "CUSTOMER_ACTION_REQUIRED"), None)
    assert req_notif is not None

    # Step 2: Complete customer action
    res_act = client.post(f"/api/recovery-cases/{case_id}/customer-action", json={"action_type": "ADD_FUNDS"})
    assert res_act.status_code == 200

    # Verify CUSTOMER_ACTION_COMPLETED notification was created
    res_notif2 = client.get("/api/notifications")
    notifs2 = res_notif2.json()["notifications"]
    comp_notif = next((n for n in notifs2 if n["case_id"] == case_id and n["type"] == "CUSTOMER_ACTION_COMPLETED"), None)
    assert comp_notif is not None
    assert comp_notif["is_read"] is False


def test_2_human_approval_and_rejection_notifications(client):
    """Test 2: HUMAN_APPROVED and HUMAN_REJECTED notifications on operator actions."""
    # Setup test case for approval
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]
    cust = Customer(external_customer_id=f"cust_h_{uid}", name=f"Human Review Cust {uid}", email=f"h_{uid}@example.com")
    db.add(cust)
    db.commit()

    pay = Payment(customer_id=cust.id, gateway_payment_id=f"pay_h_{uid}", amount=500.0, status="FAILED", failure_reason="NETWORK_TIMEOUT")
    db.add(pay)
    db.commit()

    case = RecoveryCase(customer_id=cust.id, payment_id=pay.id, revenue_at_risk=500.0, status="ESCALATED", recommended_action="RETRY")
    db.add(case)
    db.commit()
    case_id = case.id
    db.close()

    # Step 1: Approve case
    res_app = client.post(f"/api/recovery-cases/{case_id}/approve", json={"action": "RETRY"})
    assert res_app.status_code == 200

    res_notifs = client.get("/api/notifications")
    notifs = res_notifs.json()["notifications"]
    app_notif = next((n for n in notifs if n["case_id"] == case_id and n["type"] == "HUMAN_APPROVED"), None)
    assert app_notif is not None

    # Step 2: Test Rejection on a second case
    db = SessionLocal()
    uid2 = uuid.uuid4().hex[:8]
    cust2 = Customer(external_customer_id=f"cust_rej_{uid2}", name=f"Rejection Cust {uid2}")
    db.add(cust2)
    db.commit()
    pay2 = Payment(customer_id=cust2.id, gateway_payment_id=f"pay_rej_{uid2}", amount=400.0, status="FAILED")
    db.add(pay2)
    db.commit()
    case2 = RecoveryCase(customer_id=cust2.id, payment_id=pay2.id, revenue_at_risk=400.0, status="ESCALATED")
    db.add(case2)
    db.commit()
    case2_id = case2.id
    db.close()

    res_rej = client.post(f"/api/recovery-cases/{case2_id}/reject")
    assert res_rej.status_code == 200

    res_notifs2 = client.get("/api/notifications")
    notifs2 = res_notifs2.json()["notifications"]
    rej_notif = next((n for n in notifs2 if n["case_id"] == case2_id and n["type"] == "HUMAN_REJECTED"), None)
    assert rej_notif is not None


def test_3_retry_scheduled_notification_and_deduplication(client):
    """Test 3: RETRY_SCHEDULED creates one notification and prevents duplicate spam on polling/clicks."""
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]
    cust = Customer(external_customer_id=f"cust_sch_{uid}", name=f"Sched Cust {uid}", email=f"sch_{uid}@example.com")
    db.add(cust)
    db.commit()

    pay = Payment(customer_id=cust.id, gateway_payment_id=f"pay_sch_{uid}", amount=120.0, status="FAILED")
    db.add(pay)
    db.commit()

    now = datetime.now(timezone.utc)
    future = now + timedelta(hours=2)
    case = RecoveryCase(customer_id=cust.id, payment_id=pay.id, revenue_at_risk=120.0, status="RE_EVALUATING", retry_after=future)
    db.add(case)
    db.commit()
    case_id = case.id
    db.close()

    # Step 1: Operator clicks re-evaluate before retry_after
    res_sched = client.post(f"/api/recovery-cases/{case_id}/re-evaluate")
    assert res_sched.status_code == 200
    assert res_sched.json()["status"] == "SCHEDULED"

    # Verify notification created
    res_notifs = client.get("/api/notifications")
    sched_notifs = [n for n in res_notifs.json()["notifications"] if n["case_id"] == case_id and n["type"] == "RETRY_SCHEDULED"]
    assert len(sched_notifs) == 1

    # Step 2: Rapid duplicate click -> deduplication prevents duplicate notification
    res_sched2 = client.post(f"/api/recovery-cases/{case_id}/re-evaluate")
    assert res_sched2.status_code == 200
    res_notifs2 = client.get("/api/notifications")
    sched_notifs2 = [n for n in res_notifs2.json()["notifications"] if n["case_id"] == case_id and n["type"] == "RETRY_SCHEDULED"]
    assert len(sched_notifs2) == 1


def test_4_policy_blocked_notification(client):
    """Test 4: When guardrails block an action, a POLICY_BLOCKED notification is dispatched."""
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]
    cust = Customer(external_customer_id=f"cust_blk_{uid}", name=f"Blocked Cust {uid}", opted_out=True)
    db.add(cust)
    db.commit()

    pay = Payment(customer_id=cust.id, gateway_payment_id=f"pay_blk_{uid}", amount=150.0, status="FAILED")
    db.add(pay)
    db.commit()

    case = RecoveryCase(
        customer_id=cust.id,
        payment_id=pay.id,
        revenue_at_risk=150.0,
        status="PRIORITIZED",
        recommended_action="RETRY"
    )
    db.add(case)
    db.commit()
    case_id = case.id
    db.close()

    # Execute workflow -> Guardrail check should fail due to customer opt-out and dispatch POLICY_BLOCKED
    from app.services.execution_service import execution_service
    db = SessionLocal()
    run = AgentRun(case_id=case_id, status="PENDING", trigger_type="MANUAL_APPROVE", recommended_action="RETRY")
    db.add(run)
    db.commit()
    run_id = run.id
    db.close()

    execution_service.run_agent_workflow_sync(run_id)

    res_notifs = client.get("/api/notifications")
    notifs = res_notifs.json()["notifications"]
    blk_notif = next((n for n in notifs if n["case_id"] == case_id and n["type"] == "POLICY_BLOCKED"), None)
    assert blk_notif is not None

