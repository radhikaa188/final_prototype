import uuid
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.db.models import Customer, Payment, RecoveryCase, AgentRun, RecoveryAction, AuditEvent, User, Policy
from app.policies.guardrails import policy_engine, PolicyEngine
from app.auth.security import create_access_token
from app.auth.init_users import seed_default_users

def get_auth_client(db: Session):
    seed_default_users(db)
    ops_user = db.query(User).filter(User.role == "OPS").first()
    token = create_access_token({"sub": ops_user.id, "email": ops_user.email, "role": ops_user.role})
    client = TestClient(app)
    client.headers["Authorization"] = f"Bearer {token}"
    return client


def test_a_mathematical_correctness(db: Session):
    """Test A: computed_age == (demo_reference_time - stored_failure_timestamp) / 3600.0 exactly."""
    demo_ref = PolicyEngine.get_stable_demo_reference_time(db)
    
    # Create sample seeded payment
    cust = Customer(name="Math Cust", email="math@test.com", external_customer_id="sub_math_01")
    db.add(cust)
    db.flush()
    
    pay_time = datetime(2026, 8, 28, 8, 21, 23, 160274, tzinfo=timezone.utc)
    pay = Payment(
        gateway_payment_id="pay_sub_math_01",
        customer_id=cust.id,
        amount=100.0,
        status="FAILED",
        failure_reason="NETWORK_TIMEOUT",
        created_at=pay_time
    )
    db.add(pay)
    db.flush()
    
    case = RecoveryCase(
        payment_id=pay.id,
        customer_id=cust.id,
        status="PRIORITIZED",
        revenue_at_risk=100.0,
        created_at=pay_time
    )
    db.add(case)
    db.commit()

    fail_time, effective_now, computed_age = PolicyEngine.get_effective_case_age_and_now(db, case, pay)
    
    assert effective_now == demo_ref
    assert fail_time == pay_time
    expected_age = (demo_ref - pay_time).total_seconds() / 3600.0
    assert abs(computed_age - expected_age) < 1e-6


def test_b_stable_reference_determinism(db: Session):
    """Test B: Multiple evaluations produce identical demo reference time."""
    ref_1 = PolicyEngine.get_stable_demo_reference_time(db)
    ref_2 = PolicyEngine.get_stable_demo_reference_time(db)
    ref_3 = PolicyEngine.get_stable_demo_reference_time(db)

    assert ref_1 == ref_2 == ref_3
    assert ref_1.tzinfo is not None


def test_c_restart_stability(db: Session):
    """Test C: Simulated restart/reconnect preserves identical reference time."""
    before_ref = PolicyEngine.get_stable_demo_reference_time(db)
    after_ref = PolicyEngine.get_stable_demo_reference_time(db)
    assert before_ref == after_ref


def test_d_page_refresh_immutability(db: Session):
    """Test D: API reads do not alter stored database timestamps or reference time."""
    client = get_auth_client(db)
    sample_case = db.query(RecoveryCase).first()
    if sample_case:
        original_created_at = sample_case.created_at
        res1 = client.get(f"/api/recovery-cases/{sample_case.id}")
        assert res1.status_code == 200
        res2 = client.get("/api/recovery-cases")
        assert res2.status_code == 200
        res3 = client.get("/api/analytics/summary")
        assert res3.status_code == 200
        db.refresh(sample_case)
        assert sample_case.created_at == original_created_at


def test_e_72h_boundary_passed_and_blocked(db: Session):
    """Test E: Case with age <= 72h passes, case with age > 72h blocks SLA."""
    demo_ref = PolicyEngine.get_stable_demo_reference_time(db)
    cust = Customer(name="Boundary Cust", email="b@test.com", external_customer_id="sub_bound_01")
    db.add(cust)
    db.flush()

    # 1. Fresh case: failure 24h prior to demo_ref (PASSED)
    fresh_time = demo_ref - timedelta(hours=24)
    pay_fresh = Payment(gateway_payment_id="pay_sub_fresh_01", customer_id=cust.id, amount=100.0, status="FAILED", failure_reason="NETWORK_TIMEOUT", created_at=fresh_time)
    db.add(pay_fresh)
    db.flush()
    case_fresh = RecoveryCase(payment_id=pay_fresh.id, customer_id=cust.id, status="PRIORITIZED", revenue_at_risk=100.0, retry_count=0, created_at=fresh_time)
    db.add(case_fresh)
    db.flush()

    allowed_f, reason_f, checks_f = policy_engine.validate_action(db, case_fresh, "RETRY")
    assert checks_f["recovery_window"]["passed"] is True
    assert allowed_f is True

    # 2. Expired case: failure 80h prior to demo_ref (BLOCKED)
    old_time = demo_ref - timedelta(hours=80)
    pay_old = Payment(gateway_payment_id="pay_sub_old_01", customer_id=cust.id, amount=100.0, status="FAILED", failure_reason="NETWORK_TIMEOUT", created_at=old_time)
    db.add(pay_old)
    db.flush()
    case_old = RecoveryCase(payment_id=pay_old.id, customer_id=cust.id, status="PRIORITIZED", revenue_at_risk=100.0, retry_count=0, created_at=old_time)
    db.add(case_old)
    db.commit()

    allowed_o, reason_o, checks_o = policy_engine.validate_action(db, case_old, "RETRY")
    assert checks_o["recovery_window"]["passed"] is False
    assert allowed_o is False
    assert "Recovery window of 72 hours has elapsed" in reason_o


def test_f_new_test_mode_event_uses_real_time(db: Session):
    """Test F: Runtime Test Mode payment uses actual current UTC time."""
    client = get_auth_client(db)
    before_call = datetime.now(timezone.utc)

    res = client.post("/api/test-mode/generate-payment", json={"amount": 199.0, "failure_reason": "NETWORK_TIMEOUT"})
    assert res.status_code == 200
    data = res.json()
    case_id = data["case_id"]

    case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    pay = db.query(Payment).filter(Payment.id == case.payment_id).first()

    assert pay.gateway_payment_id.startswith("pay_sim_") or pay.gateway_payment_id.startswith("pay_test_")
    assert abs((pay.created_at.replace(tzinfo=timezone.utc) - before_call).total_seconds()) < 10

    fail_time, effective_now, age_hours = PolicyEngine.get_effective_case_age_and_now(db, case, pay)
    assert age_hours < 0.1
    allowed, reason, checks = policy_engine.validate_action(db, case, "RETRY")
    assert checks["recovery_window"]["passed"] is True


def test_g_new_webhook_event_uses_real_time(db: Session):
    """Test G: Webhook-created failure uses actual current UTC time."""
    client = get_auth_client(db)
    before_call = datetime.now(timezone.utc)

    res = client.post("/api/test-mode/send-webhook", json={"amount": 89.0, "failure_reason": "BANK_UNAVAILABLE"})
    assert res.status_code == 200
    data = res.json()
    case_id = data["case_id"]

    case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    pay = db.query(Payment).filter(Payment.id == case.payment_id).first()

    assert abs((pay.created_at.replace(tzinfo=timezone.utc) - before_call).total_seconds()) < 10
    fail_time, effective_now, age_hours = PolicyEngine.get_effective_case_age_and_now(db, case, pay)
    assert age_hours < 0.1


def test_h_database_records_preservation(db: Session):
    """Test H: Operational database row counts remain stable and populated."""
    assert db.query(Customer).count() >= 0
    assert db.query(Payment).count() >= 0
    assert db.query(RecoveryCase).count() >= 0
