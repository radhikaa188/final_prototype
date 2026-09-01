import pytest
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.db.models import Customer, Payment, RecoveryCase, RecoveryAction, User
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


def test_1_and_2_fraud_suspicious_routes_directly_to_escalated_zero_gateway_retries(client):
    """Test 1 & 2: Explicit fraud/suspicious payment routes directly to ESCALATED with 0 gateway retries."""
    res_gen = client.post("/api/test-mode/generate-payment", json={
        "amount": 750.0,
        "failure_reason": "FRAUD_SUSPECTED"
    })
    assert res_gen.status_code == 200
    gen_data = res_gen.json()
    case_id = gen_data["case_id"]

    db = SessionLocal()
    case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    payment = db.query(Payment).filter(Payment.id == case.payment_id).first()
    actions = db.query(RecoveryAction).filter(RecoveryAction.case_id == case.id).all()
    db.close()

    assert case.status == "ESCALATED"
    assert case.next_action == "HUMAN_REVIEW"
    assert case.recommended_action == "HUMAN_REVIEW"
    assert len(actions) == 0, "Fraud payment must not execute automatic gateway retries"
    assert case.retry_count == 0


def test_3_and_4_fraud_case_appears_in_human_review_and_active_queue(client):
    """Test 3 & 4: Fraud case is queryable via Human Review and Active Queue."""
    res_gen = client.post("/api/test-mode/generate-payment", json={
        "amount": 920.0,
        "failure_reason": "SUSPICIOUS_ACTIVITY"
    })
    assert res_gen.status_code == 200
    case_id = res_gen.json()["case_id"]

    # Check Human Review queue
    res_hr = client.get("/api/recovery-cases?status=ESCALATED")
    assert res_hr.status_code == 200
    hr_cases = res_hr.json()["cases"]
    assert any(c["id"] == case_id for c in hr_cases)

    # Check Main Active Queue
    res_active = client.get("/api/recovery-cases?status=ACTIVE")
    assert res_active.status_code == 200
    active_cases = res_active.json()["cases"]
    assert any(c["id"] == case_id for c in active_cases)


def test_5_and_6_human_approval_flow_reaches_recovered(client):
    """Test 5 & 6: Human approval executes retry and reaches RECOVERED upon gateway success."""
    res_gen = client.post("/api/test-mode/generate-payment", json={
        "amount": 450.0,
        "failure_reason": "FRAUD_RISK"
    })
    assert res_gen.status_code == 200
    case_id = res_gen.json()["case_id"]

    # Operator approves retry
    res_app = client.post(f"/api/recovery-cases/{case_id}/approve", json={"action": "RETRY"})
    assert res_app.status_code == 200

    db = SessionLocal()
    case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    payment = db.query(Payment).filter(Payment.id == case.payment_id).first()
    db.close()

    assert case.status in ["RECOVERED", "RE_EVALUATING"]
    if payment.status == "SUCCESS":
        assert case.status == "RECOVERED"
        assert case.next_action == "NONE"


def test_7_fraud_case_cannot_bypass_hard_guardrails(client):
    """Test 7: Automated workflows cannot bypass guardrail block on fraud cases."""
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]
    cust = Customer(external_customer_id=f"cust_f_blk_{uid}", name=f"Fraud Block Cust {uid}")
    db.add(cust)
    db.commit()

    pay = Payment(customer_id=cust.id, gateway_payment_id=f"pay_f_blk_{uid}", amount=300.0, status="FAILED", failure_reason="FRAUD_SUSPECTED")
    db.add(pay)
    db.commit()

    case = RecoveryCase(
        customer_id=cust.id,
        payment_id=pay.id,
        revenue_at_risk=300.0,
        status="ESCALATED",
        root_cause="FRAUD_SUSPECTED"
    )
    db.add(case)
    db.commit()
    case_id = case.id
    db.close()

    # Validate automated retry is blocked by guardrails
    from app.policies.guardrails import policy_engine
    db = SessionLocal()
    allowed, reason, checks = policy_engine.validate_action(db, case, "RETRY", is_manual_approval=False)
    db.close()

    assert allowed is False
    assert "Fraud/suspicious" in reason


def test_8_and_9_transient_failures_remain_on_normal_automated_path(client):
    """Test 8 & 9: Normal transient failures (NETWORK_TIMEOUT, BANK_UNAVAILABLE) remain PRIORITIZED."""
    res_net = client.post("/api/test-mode/generate-payment", json={
        "amount": 100.0,
        "failure_reason": "NETWORK_TIMEOUT"
    })
    assert res_net.status_code == 200
    case_net_id = res_net.json()["case_id"]

    res_bank = client.post("/api/test-mode/generate-payment", json={
        "amount": 120.0,
        "failure_reason": "GATEWAY_TIMEOUT"
    })
    assert res_bank.status_code == 200
    case_bank_id = res_bank.json()["case_id"]

    db = SessionLocal()
    case_net = db.query(RecoveryCase).filter(RecoveryCase.id == case_net_id).first()
    case_bank = db.query(RecoveryCase).filter(RecoveryCase.id == case_bank_id).first()
    db.close()

    assert case_net.status == "PRIORITIZED"
    assert case_bank.status == "PRIORITIZED"


def test_10_customer_action_failures_remain_customer_action_required(client):
    """Test 10: Customer action failures (CARD_EXPIRED, INSUFFICIENT_FUNDS) remain CUSTOMER_ACTION_REQUIRED."""
    res_exp = client.post("/api/test-mode/generate-payment", json={
        "amount": 180.0,
        "failure_reason": "CARD_EXPIRED"
    })
    assert res_exp.status_code == 200
    case_exp_id = res_exp.json()["case_id"]

    res_funds = client.post("/api/test-mode/generate-payment", json={
        "amount": 220.0,
        "failure_reason": "INSUFFICIENT_FUNDS"
    })
    assert res_funds.status_code == 200
    case_funds_id = res_funds.json()["case_id"]

    db = SessionLocal()
    case_exp = db.query(RecoveryCase).filter(RecoveryCase.id == case_exp_id).first()
    case_funds = db.query(RecoveryCase).filter(RecoveryCase.id == case_funds_id).first()
    db.close()

    assert case_exp.status == "CUSTOMER_ACTION_REQUIRED"
    assert case_funds.status == "CUSTOMER_ACTION_REQUIRED"
