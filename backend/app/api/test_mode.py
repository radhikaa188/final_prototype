import hmac
import hashlib
import json
import random
from typing import Optional, Dict, Any, Tuple
from fastapi import APIRouter, Depends, Body
from sqlalchemy.orm import Session
from app.config import settings
from app.db.session import get_db
from app.db.models import User
from app.auth.dependencies import require_role
from app.services.webhook_service import webhook_service

router = APIRouter(prefix="/test-mode", tags=["test-mode"])


def _generate_signed_webhook_payload(
    amount_override: Optional[float] = None,
    reason_override: Optional[str] = None,
    event_type: str = "payment.failed",
    custom_event_id: Optional[str] = None
) -> Tuple[Dict[str, Any], bytes, str]:
    rand_id = random.randint(10000, 99999)
    event_id = custom_event_id or f"evt_sim_{rand_id}"

    if amount_override:
        amt_float = float(amount_override)
    else:
        amt_float = random.choice([79.99, 149.00, 299.99, 499.00, 1250.00, 4999.00])

    # Convert to Razorpay paise integer
    amt_paise = int(round(amt_float * 100))

    if reason_override:
        err_code = str(reason_override).upper()
    else:
        err_code = random.choice([
            "BAD_REQUEST_ERROR",
            "GATEWAY_TIMEOUT",
            "INSUFFICIENT_FUNDS",
            "CARD_EXPIRED",
            "FRAUD_RISK"
        ])

    payload_dict = {
        "event": event_type,
        "event_id": event_id,
        "payload": {
            "payment": {
                "id": f"pay_sim_{rand_id}",
                "amount": amt_paise,
                "currency": "INR",
                "status": "failed" if event_type == "payment.failed" else "captured",
                "error_code": err_code,
                "error_description": f"Simulated payment error ({err_code})",
                "method": "card"
            },
            "customer": {
                "id": f"cust_sim_{rand_id}"
            }
        }
    }

    raw_body = json.dumps(payload_dict, separators=(',', ':')).encode('utf-8')
    secret_bytes = settings.RAZORPAY_WEBHOOK_SECRET.encode('utf-8')
    signature = hmac.new(secret_bytes, raw_body, hashlib.sha256).hexdigest()

    return payload_dict, raw_body, signature


@router.post("/generate-payment")
def generate_test_payment(
    payload: Optional[Dict[str, Any]] = Body(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["OPS", "ADMIN"]))
):
    """
    Simulates incoming payment failure event by routing through the Webhook Processing Service.
    Preserves backward compatibility with existing UI.
    """
    amount_override = payload.get("amount") if payload else None
    reason_override = payload.get("failure_reason") if payload else None

    payload_dict, raw_body, signature = _generate_signed_webhook_payload(
        amount_override=amount_override,
        reason_override=reason_override
    )

    result = webhook_service.process_razorpay_webhook(
        db=db,
        payload_data=payload_dict,
        raw_body=raw_body,
        signature=signature,
        verify_sig=True
    )

    return result


@router.post("/send-webhook")
def send_webhook_test(
    event_type: str = "payment.failed",
    amount: Optional[float] = 149.99,
    failure_reason: Optional[str] = "INSUFFICIENT_FUNDS",
    custom_event_id: Optional[str] = None,
    corrupt_signature: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["OPS", "ADMIN"]))
):
    """
    Test Mode Helper to dispatch signed simulated Razorpay Webhook events.
    Supports testing normal ingestion, duplicate event idempotency, unsupported events, and signature failures.
    """
    payload_dict, raw_body, signature = _generate_signed_webhook_payload(
        amount_override=amount,
        reason_override=failure_reason,
        event_type=event_type,
        custom_event_id=custom_event_id
    )

    if corrupt_signature:
        signature = "invalid_signature_hash_12345"

    result = webhook_service.process_razorpay_webhook(
        db=db,
        payload_data=payload_dict,
        raw_body=raw_body,
        signature=signature,
        verify_sig=True
    )

    return result
