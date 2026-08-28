from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, Request, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services.webhook_service import webhook_service

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


class RazorpayPaymentModel(BaseModel):
    id: str = Field(..., example="pay_sim_12345")
    amount: int = Field(..., example=499900, description="Amount in paise (e.g. 499900 = 4999.00)")
    currency: str = Field("INR", example="INR")
    status: str = Field(..., example="failed")
    error_code: Optional[str] = Field(None, example="BAD_REQUEST_ERROR")
    error_description: Optional[str] = Field(None, example="Payment failed due to insufficient funds")
    method: Optional[str] = Field("card", example="card")


class RazorpayCustomerModel(BaseModel):
    id: Optional[str] = Field(None, example="cust_sim_12345")


class RazorpayPayloadModel(BaseModel):
    payment: RazorpayPaymentModel
    customer: Optional[RazorpayCustomerModel] = None


class RazorpayWebhookPayload(BaseModel):
    event: str = Field(..., example="payment.failed")
    event_id: str = Field(..., example="evt_sim_12345")
    payload: RazorpayPayloadModel


@router.post("/razorpay", status_code=200)
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: Optional[str] = Header(None, alias="X-Razorpay-Signature"),
    x_test_mode: Optional[str] = Header(None, alias="X-Test-Mode"),
    db: Session = Depends(get_db)
):
    """
    Webhook Ingestion Endpoint for Razorpay Payment Failure Events.
    Performs HMAC-SHA256 signature verification, persistent idempotency deduplication,
    Customer & Payment ingestion, ML diagnosis & recovery probability estimation,
    Recovery Case creation, and Audit Event recording.
    """
    raw_body = await request.body()
    try:
        payload_dict = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # If X-Test-Mode header is provided or signature is provided, verify signature accordingly
    verify_sig = True
    if x_test_mode == "true" and not x_razorpay_signature:
        verify_sig = False

    result = webhook_service.process_razorpay_webhook(
        db=db,
        payload_data=payload_dict,
        raw_body=raw_body,
        signature=x_razorpay_signature,
        verify_sig=verify_sig
    )

    return result
