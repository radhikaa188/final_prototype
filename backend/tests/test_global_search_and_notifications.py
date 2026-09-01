import pytest
import uuid
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.db.models import Customer, Payment, RecoveryCase, Notification, User
from app.auth.security import create_access_token
from app.auth.init_users import seed_default_users
from app.services.notification_service import notification_service


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


def test_1_global_search_by_payment_id(client):
    """Test 1: Search queries database by Payment ID and Gateway Payment ID."""
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]
    cust = Customer(external_customer_id=f"cust_s_{uid}", name=f"Search Cust {uid}", email=f"s_{uid}@example.com")
    db.add(cust)
    db.commit()

    pay = Payment(
        customer_id=cust.id,
        gateway_payment_id=f"pay_gw_search_{uid}",
        amount=650.0,
        status="FAILED",
        failure_reason="NETWORK_TIMEOUT"
    )
    db.add(pay)
    db.commit()

    case = RecoveryCase(
        customer_id=cust.id,
        payment_id=pay.id,
        revenue_at_risk=650.0,
        status="PRIORITIZED"
    )
    db.add(case)
    db.commit()
    case_id = case.id
    payment_id = pay.id
    gw_id = pay.gateway_payment_id
    db.close()

    # Search by gateway payment ID
    res = client.get(f"/api/search?q={gw_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["total_results"] >= 1
    found_pay = next((p for p in data["payments"] if p["id"] == payment_id), None)
    assert found_pay is not None
    assert found_pay["gateway_payment_id"] == gw_id
    assert found_pay["amount"] == 650.0
    assert found_pay["recovery_case_id"] == case_id



def test_2_global_search_by_customer_id_and_name(client):
    """Test 2: Search queries database by Customer external ID and Name."""
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]
    cust = Customer(external_customer_id=f"cust_unique_{uid}", name=f"Acme Corp {uid}", email=f"acme_{uid}@example.com")
    db.add(cust)
    db.commit()
    cust_id = cust.id
    db.close()

    # Search by Name
    res = client.get(f"/api/search?q=Acme+Corp+{uid}")
    assert res.status_code == 200
    data = res.json()
    assert data["total_results"] >= 1
    found_cust = next((c for c in data["customers"] if c["id"] == cust_id), None)
    assert found_cust is not None
    assert found_cust["name"] == f"Acme Corp {uid}"

    # Search by External Customer ID
    res_ext = client.get(f"/api/search?q=cust_unique_{uid}")
    assert res_ext.status_code == 200
    assert any(c["id"] == cust_id for c in res_ext.json()["customers"])


def test_3_global_search_by_recovery_case_id(client):
    """Test 3: Search queries database by RecoveryCase ID."""
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]
    cust = Customer(external_customer_id=f"cust_rc_{uid}", name=f"Case Search Cust {uid}")
    db.add(cust)
    db.commit()

    pay = Payment(customer_id=cust.id, gateway_payment_id=f"pay_rc_{uid}", amount=199.0, status="FAILED", failure_reason="CARD_EXPIRED")
    db.add(pay)
    db.commit()

    case = RecoveryCase(
        customer_id=cust.id,
        payment_id=pay.id,
        revenue_at_risk=199.0,
        status="CUSTOMER_ACTION_REQUIRED",
        root_cause="EXPIRED_CARD"
    )
    db.add(case)
    db.commit()
    case_id = case.id
    db.close()

    res = client.get(f"/api/search?q={case_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["total_results"] >= 1
    found_case = next((c for c in data["recovery_cases"] if c["id"] == case_id), None)
    assert found_case is not None
    assert found_case["status"] == "CUSTOMER_ACTION_REQUIRED"


def test_4_global_search_nonexistent_query_returns_empty(client):
    """Test 4: Non-matching random string returns empty result structure."""
    nonexistent = f"nonexistent_random_token_{uuid.uuid4().hex}"
    res = client.get(f"/api/search?q={nonexistent}")
    assert res.status_code == 200
    data = res.json()
    assert data["total_results"] == 0
    assert len(data["payments"]) == 0
    assert len(data["customers"]) == 0
    assert len(data["recovery_cases"]) == 0


def test_5_notifications_api_and_read_state(client):
    """Test 5: Real database-backed notification lifecycle, unread counts, and mark-as-read."""
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]
    cust = Customer(external_customer_id=f"cust_notif_{uid}", name=f"Notif Cust {uid}", email=f"notif_{uid}@example.com")
    db.add(cust)
    db.commit()

    pay = Payment(customer_id=cust.id, gateway_payment_id=f"pay_notif_{uid}", amount=300.0, status="FAILED")
    db.add(pay)
    db.commit()

    case = RecoveryCase(customer_id=cust.id, payment_id=pay.id, revenue_at_risk=300.0, status="CUSTOMER_ACTION_REQUIRED")
    db.add(case)
    db.commit()

    # Send a real notification
    notif = notification_service.send_notification(
        db=db,
        case_id=case.id,
        customer_id=cust.id,
        type_="CUSTOMER_ACTION_REQUIRED",
        channel="IN_APP",
        recipient=cust.email
    )
    notif_id = notif.id
    db.close()

    # Step 1: List notifications & check unread
    res = client.get("/api/notifications")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    target_notif = next((n for n in data["notifications"] if n["id"] == notif_id), None)
    assert target_notif is not None
    assert target_notif["is_read"] is False
    assert target_notif["type"] == "CUSTOMER_ACTION_REQUIRED"

    # Step 2: Mark single notification as read
    res_read = client.post(f"/api/notifications/{notif_id}/read")
    assert res_read.status_code == 200
    assert res_read.json()["is_read"] is True

    # Step 3: Verify notification is now marked read
    res_after = client.get("/api/notifications")
    data_after = res_after.json()
    target_after = next((n for n in data_after["notifications"] if n["id"] == notif_id), None)
    assert target_after["is_read"] is True
    assert target_after["clicked_at"] is not None

    # Step 4: Mark all as read
    res_all = client.post("/api/notifications/mark-all-read")
    assert res_all.status_code == 200
    res_final = client.get("/api/notifications")
    assert res_final.json()["unread_count"] == 0
