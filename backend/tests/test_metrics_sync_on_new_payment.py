import pytest
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.db.models import Customer, Payment, RecoveryCase, RecoveryAction, User
from app.auth.security import create_access_token
from app.auth.init_users import seed_default_users
from app.api.dashboard import ACTIVE_STATUSES


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


def test_1_customer_action_payment_syncs_active_cases_and_kpis(client):
    """Test 1: New Test Mode payment requiring customer action increments Active Cases, Recovery Cases, and Customer Action count."""
    # Step 1: Query initial baseline
    res_summary_before = client.get("/api/dashboard/summary")
    assert res_summary_before.status_code == 200
    sum_before = res_summary_before.json()
    
    res_funnel_before = client.get("/api/dashboard/funnel")
    assert res_funnel_before.status_code == 200
    funnel_before = {item["stage"]: item["count"] for item in res_funnel_before.json()}

    res_cases_before = client.get("/api/recovery-cases?status=CUSTOMER_ACTION_REQUIRED")
    assert res_cases_before.status_code == 200
    cust_actions_before = len(res_cases_before.json()["cases"])

    # Step 2: Generate Test Mode Payment with INSUFFICIENT_FUNDS
    res_gen = client.post("/api/test-mode/generate-payment", json={
        "amount": 250.0,
        "failure_reason": "INSUFFICIENT_FUNDS"
    })
    assert res_gen.status_code == 200
    gen_data = res_gen.json()
    assert gen_data["status"] == "success"
    case_id = gen_data["case_id"]

    # Step 3: Fetch updated KPIs
    res_summary_after = client.get("/api/dashboard/summary")
    assert res_summary_after.status_code == 200
    sum_after = res_summary_after.json()

    res_funnel_after = client.get("/api/dashboard/funnel")
    assert res_funnel_after.status_code == 200
    funnel_after = {item["stage"]: item["count"] for item in res_funnel_after.json()}

    res_cases_after = client.get("/api/recovery-cases?status=CUSTOMER_ACTION_REQUIRED")
    assert res_cases_after.status_code == 200
    cust_actions_after = len(res_cases_after.json()["cases"])

    # Step 4: Verify exact delta increments
    assert sum_after["active_cases"] == sum_before["active_cases"] + 1
    assert sum_after["total_cases"] == sum_before["total_cases"] + 1
    assert sum_after["revenue_at_risk"] == round(sum_before["revenue_at_risk"] + 250.0, 2)
    assert sum_after["recoverable_revenue"] > sum_before["recoverable_revenue"]
    assert sum_after["revenue_recovered"] == sum_before["revenue_recovered"]

    assert funnel_after["Failed Payments"] == funnel_before["Failed Payments"] + 1
    assert funnel_after["Recovery Cases"] == funnel_before["Recovery Cases"] + 1
    assert funnel_after["Eligible Cases"] == funnel_before["Eligible Cases"] + 1
    assert cust_actions_after == cust_actions_before + 1

    # Verify case details
    db = SessionLocal()
    case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    assert case is not None
    assert case.status == "CUSTOMER_ACTION_REQUIRED"
    assert case.status in ACTIVE_STATUSES
    db.close()


def test_2_transient_payment_syncs_active_cases_and_kpis(client):
    """Test 2: New Test Mode payment with transient failure increments Active Cases & Prioritized Queue."""
    res_summary_before = client.get("/api/dashboard/summary")
    sum_before = res_summary_before.json()

    res_gen = client.post("/api/test-mode/generate-payment", json={
        "amount": 320.0,
        "failure_reason": "GATEWAY_TIMEOUT"
    })
    assert res_gen.status_code == 200
    gen_data = res_gen.json()
    assert gen_data["status"] == "success"
    case_id = gen_data["case_id"]

    res_summary_after = client.get("/api/dashboard/summary")
    sum_after = res_summary_after.json()

    assert sum_after["active_cases"] == sum_before["active_cases"] + 1
    assert sum_after["total_cases"] == sum_before["total_cases"] + 1
    assert sum_after["revenue_at_risk"] == round(sum_before["revenue_at_risk"] + 320.0, 2)

    db = SessionLocal()
    case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    assert case.status == "PRIORITIZED"
    assert case.status in ACTIVE_STATUSES
    db.close()


def test_3_recovered_case_transitions_out_of_active_into_recovered(client):
    """Test 3: Recovered case decrements Active Cases and increments Recovered Cases and Revenue Recovered."""
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]
    cust = Customer(external_customer_id=f"cust_m_{uid}", name=f"Metrics Cust {uid}", email=f"m_{uid}@example.com")
    db.add(cust)
    db.commit()

    pay = Payment(customer_id=cust.id, gateway_payment_id=f"pay_m_{uid}", amount=500.0, status="FAILED", failure_reason="NETWORK_TIMEOUT")
    db.add(pay)
    db.commit()

    case = RecoveryCase(
        customer_id=cust.id,
        payment_id=pay.id,
        revenue_at_risk=500.0,
        expected_recovery=400.0,
        status="PRIORITIZED",
        next_action="RETRY",
        recommended_action="RETRY",
        priority_score=88.0,
        recovery_probability=0.8
    )
    db.add(case)
    db.commit()
    case_id = case.id
    db.close()

    res_before = client.get("/api/dashboard/summary")
    sum_before = res_before.json()

    # Approve and execute retry with simulated gateway SUCCESS
    with patch("app.services.gateway_simulator.SimulatedPaymentGateway.process_retry") as mock_retry:
        mock_retry.return_value = {
            "status": "SUCCESS",
            "transaction_id": f"txn_succ_{uid}",
            "amount_recovered": 500.0,
            "gateway_code": "200_OK",
            "message": "Payment captured successfully."
        }
        res_exec = client.post(f"/api/recovery-cases/{case_id}/approve", json={"action": "RETRY"})
        assert res_exec.status_code == 200

    res_after = client.get("/api/dashboard/summary")
    sum_after = res_after.json()

    # Active cases decreases by 1, Revenue recovered increases by 500.0
    assert sum_after["active_cases"] == sum_before["active_cases"] - 1
    assert sum_after["revenue_recovered"] == round(sum_before["revenue_recovered"] + 500.0, 2)


def test_4_stopped_case_transitions_out_of_active_without_recovered_revenue(client):
    """Test 4: Stopped case decrements Active Cases without inflating Revenue Recovered."""
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]
    cust = Customer(external_customer_id=f"cust_stop_{uid}", name=f"Stopped Cust {uid}", email=f"stop_{uid}@example.com")
    db.add(cust)
    db.commit()

    pay = Payment(customer_id=cust.id, gateway_payment_id=f"pay_stop_{uid}", amount=150.0, status="FAILED", failure_reason="NETWORK_TIMEOUT")
    db.add(pay)
    db.commit()

    case = RecoveryCase(
        customer_id=cust.id,
        payment_id=pay.id,
        revenue_at_risk=150.0,
        expected_recovery=120.0,
        status="RE_EVALUATING",
        retry_count=2,  # Next failure reaches max retries (3) -> STOPPED
        next_action="RE_EVALUATE",
        recommended_action="RETRY"
    )
    db.add(case)
    db.commit()
    case_id = case.id
    db.close()

    res_before = client.get("/api/dashboard/summary")
    sum_before = res_before.json()

    # Advance retry_after and execute re-evaluation with simulated gateway FAILURE
    db = SessionLocal()
    c_edit = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    c_edit.retry_after = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()
    db.close()

    with patch("app.services.gateway_simulator.SimulatedPaymentGateway.process_retry") as mock_retry:
        mock_retry.return_value = {
            "status": "FAILED",
            "transaction_id": f"txn_fail_{uid}",
            "amount_recovered": 0.0,
            "gateway_code": "DECLINED",
            "message": "Payment retry failed: NETWORK_TIMEOUT"
        }
        res_exec = client.post(f"/api/recovery-cases/{case_id}/re-evaluate")
        assert res_exec.status_code == 200

    res_after = client.get("/api/dashboard/summary")
    sum_after = res_after.json()

    # Active cases decreases by 1, Revenue recovered unchanged
    assert sum_after["active_cases"] == sum_before["active_cases"] - 1
    assert sum_after["revenue_recovered"] == sum_before["revenue_recovered"]

    db = SessionLocal()
    final_case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    assert final_case.status == "STOPPED"
    db.close()
