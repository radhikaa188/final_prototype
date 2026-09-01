import pytest
import uuid
from unittest.mock import patch
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.db.models import Customer, Payment, RecoveryCase, User
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


def test_1_active_prioritized_case_in_active_not_recovered(client):
    """Test 1 — Active case: PRIORITIZED appears in Active, does not appear in Recovered."""
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]
    customer = Customer(external_customer_id=f"cust_{uid}", name=f"Test Cust {uid}", email=f"cust_{uid}@example.com", lifetime_value=1200.0)
    db.add(customer)
    db.commit()

    payment = Payment(customer_id=customer.id, gateway_payment_id=f"pay_{uid}", amount=150.0, status="FAILED", failure_reason="NETWORK_TIMEOUT")
    db.add(payment)
    db.commit()

    case = RecoveryCase(
        customer_id=customer.id,
        payment_id=payment.id,
        revenue_at_risk=150.0,
        status="PRIORITIZED",
        next_action="RETRY",
        recommended_action="RETRY",
        priority_score=95.0,
        recovery_probability=0.85
    )
    db.add(case)
    db.commit()
    case_id = case.id
    db.close()

    # Query Active (default)
    res_active = client.get("/api/recovery-cases")
    assert res_active.status_code == 200
    active_ids = [c["id"] for c in res_active.json()["cases"]]
    assert case_id in active_ids

    # Query Recovered
    res_rec = client.get("/api/recovery-cases?status=RECOVERED")
    assert res_rec.status_code == 200
    rec_ids = [c["id"] for c in res_rec.json()["cases"]]
    assert case_id not in rec_ids


def test_2_customer_action_in_active_and_customer_actions_not_recovered(client):
    """Test 2 — Customer Action: CUSTOMER_ACTION_REQUIRED appears in Active, appears in Customer Actions, not Recovered."""
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]
    customer = Customer(external_customer_id=f"cust_{uid}", name=f"Test Cust {uid}", email=f"cust_{uid}@example.com", lifetime_value=2000.0)
    db.add(customer)
    db.commit()

    payment = Payment(customer_id=customer.id, gateway_payment_id=f"pay_{uid}", amount=250.0, status="FAILED", failure_reason="CARD_EXPIRED")
    db.add(payment)
    db.commit()

    case = RecoveryCase(
        customer_id=customer.id,
        payment_id=payment.id,
        revenue_at_risk=250.0,
        status="CUSTOMER_ACTION_REQUIRED",
        next_action="WAIT_FOR_CUSTOMER_ACTION",
        recommended_action="CUSTOMER_NUDGE",
        customer_action_required=True,
        customer_action_type="UPDATE_CARD",
        customer_action_status="PENDING",
        priority_score=82.0,
        recovery_probability=0.70
    )
    db.add(case)
    db.commit()
    case_id = case.id
    db.close()

    # Query Active
    res_active = client.get("/api/recovery-cases")
    assert res_active.status_code == 200
    active_ids = [c["id"] for c in res_active.json()["cases"]]
    assert case_id in active_ids

    # Query Customer Actions
    res_cust = client.get("/api/recovery-cases?status=CUSTOMER_ACTION_REQUIRED")
    assert res_cust.status_code == 200
    cust_ids = [c["id"] for c in res_cust.json()["cases"]]
    assert case_id in cust_ids

    # Query Recovered
    res_rec = client.get("/api/recovery-cases?status=RECOVERED")
    assert res_rec.status_code == 200
    rec_ids = [c["id"] for c in res_rec.json()["cases"]]
    assert case_id not in rec_ids


def test_3_human_review_in_active_and_human_review_not_recovered(client):
    """Test 3 — Human Review: ESCALATED appears in Active, appears in Human Review, not Recovered."""
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]
    customer = Customer(external_customer_id=f"cust_{uid}", name=f"Test Cust {uid}", email=f"cust_{uid}@example.com", lifetime_value=5000.0)
    db.add(customer)
    db.commit()

    payment = Payment(customer_id=customer.id, gateway_payment_id=f"pay_{uid}", amount=3500.0, status="FAILED", failure_reason="HIGH_RISK_SUSPECTED")
    db.add(payment)
    db.commit()

    case = RecoveryCase(
        customer_id=customer.id,
        payment_id=payment.id,
        revenue_at_risk=3500.0,
        status="ESCALATED",
        next_action="HUMAN_REVIEW",
        recommended_action="HUMAN_REVIEW",
        priority_score=74.0,
        recovery_probability=0.55
    )
    db.add(case)
    db.commit()
    case_id = case.id
    db.close()

    # Query Active
    res_active = client.get("/api/recovery-cases")
    assert res_active.status_code == 200
    active_ids = [c["id"] for c in res_active.json()["cases"]]
    assert case_id in active_ids

    # Query Human Review (NEEDS_REVIEW)
    res_hr = client.get("/api/recovery-cases?status=NEEDS_REVIEW")
    assert res_hr.status_code == 200
    hr_ids = [c["id"] for c in res_hr.json()["cases"]]
    assert case_id in hr_ids

    # Query Recovered
    res_rec = client.get("/api/recovery-cases?status=RECOVERED")
    assert res_rec.status_code == 200
    rec_ids = [c["id"] for c in res_rec.json()["cases"]]
    assert case_id not in rec_ids


def test_4_successful_recovery_moves_from_active_to_recovered(client):
    """Test 4 — Successful recovery: ACTIVE case -> gateway SUCCESS -> RECOVERED -> disappears from Active, appears in Recovered."""
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]
    customer = Customer(external_customer_id=f"cust_{uid}", name=f"Test Cust {uid}", email=f"cust_{uid}@example.com", lifetime_value=3000.0)
    db.add(customer)
    db.commit()

    payment = Payment(customer_id=customer.id, gateway_payment_id=f"pay_{uid}", amount=400.0, status="FAILED", failure_reason="NETWORK_TIMEOUT")
    db.add(payment)
    db.commit()

    case = RecoveryCase(
        customer_id=customer.id,
        payment_id=payment.id,
        revenue_at_risk=400.0,
        status="PRIORITIZED",
        next_action="RETRY",
        recommended_action="RETRY",
        priority_score=91.0,
        recovery_probability=0.88
    )
    db.add(case)
    db.commit()
    case_id = case.id
    db.close()

    # Before recovery: visible in Active
    res_before = client.get("/api/recovery-cases")
    assert case_id in [c["id"] for c in res_before.json()["cases"]]

    # Execute recovery via approve -> simulated gateway success
    with patch("app.services.gateway_simulator.SimulatedPaymentGateway.process_retry") as mock_retry:
        mock_retry.return_value = {
            "status": "SUCCESS",
            "transaction_id": f"txn_succ_{uid}",
            "amount_recovered": 400.0,
            "gateway_code": "200_OK",
            "message": "Payment captured successfully."
        }
        res_exec = client.post(f"/api/recovery-cases/{case_id}/approve", json={"action": "RETRY"})
        assert res_exec.status_code == 200

    # After recovery: verify database state
    db = SessionLocal()
    updated_case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    updated_pay = db.query(Payment).filter(Payment.id == updated_case.payment_id).first()
    assert updated_case.status == "RECOVERED"

    assert updated_case.next_action == "NONE"
    assert updated_pay.status == "SUCCESS"
    db.close()


    # After recovery: disappears from Active (default)
    res_after_active = client.get("/api/recovery-cases")
    assert case_id not in [c["id"] for c in res_after_active.json()["cases"]]

    # After recovery: appears in Recovered
    res_after_rec = client.get("/api/recovery-cases?status=RECOVERED")
    assert case_id in [c["id"] for c in res_after_rec.json()["cases"]]


def test_5_failed_recovery_remains_in_active_not_recovered(client):
    """Test 5 — Failed recovery: RETRY -> FAILED -> remains Active, not Recovered."""
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]
    customer = Customer(external_customer_id=f"cust_{uid}", name=f"Test Cust {uid}", email=f"cust_{uid}@example.com", lifetime_value=1000.0)
    db.add(customer)
    db.commit()

    payment = Payment(customer_id=customer.id, gateway_payment_id=f"pay_{uid}", amount=300.0, status="FAILED", failure_reason="BANK_UNAVAILABLE")
    db.add(payment)
    db.commit()

    case = RecoveryCase(
        customer_id=customer.id,
        payment_id=payment.id,
        revenue_at_risk=300.0,
        status="PRIORITIZED",
        next_action="RETRY",
        recommended_action="RETRY",
        retry_count=1,  # count < 3 so still active
        priority_score=60.0,
        recovery_probability=0.50
    )
    db.add(case)
    db.commit()
    case_id = case.id
    db.close()

    # Query Active
    res_active = client.get("/api/recovery-cases")
    assert case_id in [c["id"] for c in res_active.json()["cases"]]

    # Query Recovered
    res_rec = client.get("/api/recovery-cases?status=RECOVERED")
    assert case_id not in [c["id"] for c in res_rec.json()["cases"]]


def test_6_stopped_case_in_stopped_not_recovered(client):
    """Test 6 — Stopped: STOPPED appears in Stopped, not Recovered or default Active."""
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]
    customer = Customer(external_customer_id=f"cust_{uid}", name=f"Test Cust {uid}", email=f"cust_{uid}@example.com", lifetime_value=500.0)
    db.add(customer)
    db.commit()

    payment = Payment(customer_id=customer.id, gateway_payment_id=f"pay_{uid}", amount=200.0, status="FAILED", failure_reason="ACCOUNT_BLOCKED")
    db.add(payment)
    db.commit()

    case = RecoveryCase(
        customer_id=customer.id,
        payment_id=payment.id,
        revenue_at_risk=200.0,
        status="STOPPED",
        next_action="NONE",
        recommended_action="STOP",
        closed_at=datetime.now(timezone.utc),
        priority_score=10.0,
        recovery_probability=0.05
    )
    db.add(case)
    db.commit()
    case_id = case.id
    db.close()

    # Query default Active
    res_active = client.get("/api/recovery-cases")
    assert case_id not in [c["id"] for c in res_active.json()["cases"]]

    # Query Stopped
    res_stopped = client.get("/api/recovery-cases?status=STOPPED")
    assert case_id in [c["id"] for c in res_stopped.json()["cases"]]

    # Query Recovered
    res_rec = client.get("/api/recovery-cases?status=RECOVERED")
    assert case_id not in [c["id"] for c in res_rec.json()["cases"]]


def test_7_queue_priority_ordering(client):
    """Test 7 — Queue priority: Active cases remain sorted by the existing ML priority score."""
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]
    cust = Customer(external_customer_id=f"cust_ord_{uid}", name=f"Ordering Cust {uid}", email=f"ord_{uid}@example.com")
    db.add(cust)
    db.commit()

    pay1 = Payment(customer_id=cust.id, gateway_payment_id=f"pay1_ord_{uid}", amount=100.0, status="FAILED", failure_reason="NETWORK_TIMEOUT")
    pay2 = Payment(customer_id=cust.id, gateway_payment_id=f"pay2_ord_{uid}", amount=200.0, status="FAILED", failure_reason="NETWORK_TIMEOUT")
    db.add_all([pay1, pay2])
    db.commit()

    c1 = RecoveryCase(customer_id=cust.id, payment_id=pay1.id, revenue_at_risk=100.0, status="PRIORITIZED", priority_score=35.0)
    c2 = RecoveryCase(customer_id=cust.id, payment_id=pay2.id, revenue_at_risk=200.0, status="PRIORITIZED", priority_score=92.0)
    db.add_all([c1, c2])
    db.commit()
    db.close()

    res_active = client.get("/api/recovery-cases")
    assert res_active.status_code == 200
    cases = res_active.json()["cases"]
    assert len(cases) >= 2

    # Check strictly non-ascending priority score
    scores = [c["priority_score"] for c in cases]
    assert scores == sorted(scores, reverse=True)

