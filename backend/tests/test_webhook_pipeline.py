import os
import sys
import hmac
import hashlib
import json
import urllib.request
import urllib.error

sys.path.insert(0, 'backend')
from app.config import settings
from app.db.session import engine, Base
from app.db import models
from sqlalchemy import text

# Ensure all database tables including webhook_events exist
Base.metadata.create_all(bind=engine)


def run_webhook_pipeline_tests():
    print("================================================================")
    print("   RECOVERAI — AUTOMATED WEBHOOK INGESTION SUITE LIVE TEST      ")
    print("================================================================")

    SECRET = settings.RAZORPAY_WEBHOOK_SECRET
    BASE_URL = "http://127.0.0.1:8000/api"

    # Helper function to generate signed webhook request
    def make_signed_request(endpoint: str, payload_dict: dict, signature_override: str = None):
        raw_body = json.dumps(payload_dict, separators=(',', ':')).encode('utf-8')
        if signature_override is not None:
            sig = signature_override
        else:
            sig = hmac.new(SECRET.encode('utf-8'), raw_body, hashlib.sha256).hexdigest()

        headers = {
            "Content-Type": "application/json",
            "X-Razorpay-Signature": sig
        }
        req = urllib.request.Request(f"{BASE_URL}{endpoint}", data=raw_body, headers=headers)
        return req, raw_body, sig

    # Step 1: Capture DB & Analytics State BEFORE Tests
    with engine.connect() as conn:
        pay_before = conn.execute(text("SELECT COUNT(*) FROM payments")).scalar()
        case_before = conn.execute(text("SELECT COUNT(*) FROM recovery_cases")).scalar()
        audit_before = conn.execute(text("SELECT COUNT(*) FROM audit_events")).scalar()
        web_before = conn.execute(text("SELECT COUNT(*) FROM webhook_events")).scalar()

    dash_before = json.loads(urllib.request.urlopen(f"{BASE_URL}/dashboard/summary").read())

    print(f"\n[BEFORE TEST STATE]")
    print(f" Payments Count      : {pay_before}")
    print(f" Cases Count         : {case_before}")
    print(f" Audit Events Count  : {audit_before}")
    print(f" Webhook Events Count: {web_before}")
    print(f" Revenue at Risk     : ${dash_before['revenue_at_risk']:,.2f}")
    print(f" Recoverable Revenue : ${dash_before['recoverable_revenue']:,.2f}")

    # TEST A: Valid Ingestion of payment.failed Event
    print("\n----------------------------------------------------------------")
    print(" TEST A: Valid Signed Webhook Ingestion (payment.failed)")
    print("----------------------------------------------------------------")
    test_evt_id = f"evt_live_test_{os.urandom(4).hex()}"
    test_pay_id = f"pay_live_test_{os.urandom(4).hex()}"
    test_cust_id = f"cust_live_test_{os.urandom(4).hex()}"

    valid_payload = {
        "event": "payment.failed",
        "event_id": test_evt_id,
        "payload": {
            "payment": {
                "id": test_pay_id,
                "amount": 299900,  # 2999.00 INR
                "currency": "INR",
                "status": "failed",
                "error_code": "GATEWAY_TIMEOUT",
                "error_description": "Gateway connection timed out",
                "method": "card"
            },
            "customer": {
                "id": test_cust_id
            }
        }
    }

    req_a, _, _ = make_signed_request("/webhooks/razorpay", valid_payload)
    res_a = urllib.request.urlopen(req_a)
    status_a = res_a.getcode()
    body_a = json.loads(res_a.read())

    print(f" HTTP Status        : {status_a}")
    print(f" Ingestion Response : {json.dumps(body_a, indent=2)}")

    assert status_a == 200, f"Expected 200, got {status_a}"
    assert body_a["status"] == "success", f"Expected success status, got {body_a['status']}"
    assert body_a["event_id"] == test_evt_id
    assert body_a["amount"] == 2999.00
    assert "recovery_probability" in body_a
    assert "expected_recovery" in body_a
    assert "recommended_action" in body_a
    print(" >>> TEST A PASSED: Valid webhook ingested successfully!")

    # TEST B: Persistent Idempotency Check (Re-sending exact same webhook)
    print("\n----------------------------------------------------------------")
    print(" TEST B: Idempotency Verification (Duplicate Event Ingestion)")
    print("----------------------------------------------------------------")
    req_b, _, _ = make_signed_request("/webhooks/razorpay", valid_payload)
    res_b = urllib.request.urlopen(req_b)
    status_b = res_b.getcode()
    body_b = json.loads(res_b.read())

    print(f" HTTP Status        : {status_b}")
    print(f" Idempotent Response: {json.dumps(body_b, indent=2)}")

    assert status_b == 200
    assert body_b["status"] == "idempotent_ignored"
    assert body_b["event_id"] == test_evt_id
    print(" >>> TEST B PASSED: Duplicate webhook event safely ignored!")

    # TEST C: Invalid HMAC Signature Rejection
    print("\n----------------------------------------------------------------")
    print(" TEST C: Signature Verification (Invalid HMAC-SHA256 Secret)")
    print("----------------------------------------------------------------")
    invalid_sig_payload = {
        "event": "payment.failed",
        "event_id": f"evt_invalid_{os.urandom(4).hex()}",
        "payload": {"payment": {"id": "pay_fake", "amount": 1000, "status": "failed"}}
    }
    req_c, _, _ = make_signed_request("/webhooks/razorpay", invalid_sig_payload, signature_override="bad_sig_hash_000")
    try:
        urllib.request.urlopen(req_c)
        print(" ERROR: Expected HTTP 401, but request succeeded!")
        assert False
    except urllib.error.HTTPError as err:
        print(f" HTTP Status        : {err.code}")
        print(f" Error Detail       : {err.read().decode('utf-8')}")
        assert err.code == 401
        print(" >>> TEST C PASSED: Invalid signature rejected with HTTP 401!")

    # TEST D: Unsupported Event Type
    print("\n----------------------------------------------------------------")
    print(" TEST D: Unsupported Event Handling (payment.captured)")
    print("----------------------------------------------------------------")
    unsupported_evt_id = f"evt_unsupported_{os.urandom(4).hex()}"
    unsupported_payload = {
        "event": "payment.captured",
        "event_id": unsupported_evt_id,
        "payload": {"payment": {"id": "pay_captured_123", "amount": 5000, "status": "captured"}}
    }
    req_d, _, _ = make_signed_request("/webhooks/razorpay", unsupported_payload)
    res_d = urllib.request.urlopen(req_d)
    status_d = res_d.getcode()
    body_d = json.loads(res_d.read())

    print(f" HTTP Status        : {status_d}")
    print(f" Response           : {json.dumps(body_d, indent=2)}")

    assert status_d == 200
    assert body_d["status"] == "ignored"
    assert body_d["reason"] == "unsupported_event_type"
    print(" >>> TEST D PASSED: Unsupported event safely acknowledged and ignored!")

    # TEST E: Database & Downstream Pipeline Verification
    print("\n----------------------------------------------------------------")
    print(" TEST E: Database Persistence & Downstream ML/Analytics")
    print("----------------------------------------------------------------")
    with engine.connect() as conn:
        pay_after = conn.execute(text("SELECT COUNT(*) FROM payments")).scalar()
        case_after = conn.execute(text("SELECT COUNT(*) FROM recovery_cases")).scalar()
        audit_after = conn.execute(text("SELECT COUNT(*) FROM audit_events")).scalar()
        web_after = conn.execute(text("SELECT COUNT(*) FROM webhook_events")).scalar()

        pay_rec = conn.execute(text("SELECT * FROM payments WHERE gateway_payment_id = :gid"), {"gid": test_pay_id}).mappings().first()
        case_rec = conn.execute(text("SELECT * FROM recovery_cases WHERE payment_id = :pid"), {"pid": pay_rec["id"]}).mappings().first()
        web_rec = conn.execute(text("SELECT * FROM webhook_events WHERE event_id = :eid"), {"eid": test_evt_id}).mappings().first()

    dash_after = json.loads(urllib.request.urlopen(f"{BASE_URL}/dashboard/summary").read())

    print(f" Payments Delta      : {pay_after - pay_before} (Expected: +1)")
    print(f" Cases Delta         : {case_after - case_before} (Expected: +1)")
    print(f" Audit Events Delta  : {audit_after - audit_before} (Expected: +3)")
    print(f" Webhook Events Delta: {web_after - web_before} (Expected: +2)")
    print(f" Revenue at Risk Delta: +${dash_after['revenue_at_risk'] - dash_before['revenue_at_risk']:,.2f} (Expected: +$2,999.00)")
    print(f"\n [Persisted Case ML Telemetry]")
    print(f"  Root Cause Diagnosed  : {case_rec['root_cause']} (Conf: {case_rec['root_cause_confidence']})")
    print(f"  P(Recovery) Score     : {case_rec['recovery_probability']}")
    print(f"  Expected Recovery Rev : ${case_rec['expected_recovery']:,.2f}")
    print(f"  Priority Score        : {case_rec['priority_score']}")
    print(f"  Recommended Action    : {case_rec['recommended_action']}")

    assert pay_after == pay_before + 1
    assert case_after == case_before + 1
    assert web_rec["status"] == "PROCESSED"
    assert round(dash_after['revenue_at_risk'] - dash_before['revenue_at_risk'], 2) == 2999.00
    print(" >>> TEST E PASSED: Database persistence & ML pipeline verified!")

    print("\n================================================================")
    print("   ALL 5 WEBHOOK PIPELINE INTEGRATION TESTS PASSED SUCCESSFULLY! ")
    print("================================================================")


if __name__ == "__main__":
    run_webhook_pipeline_tests()
