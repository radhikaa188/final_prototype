import hmac
import hashlib
import random
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Tuple
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.config import settings
from app.db.models import Customer, Payment, RecoveryCase, WebhookEvent
from app.ml.predictor import predictor
from app.agents.recovery_agent import recovery_agent
from app.policies.guardrails import policy_engine
from app.services.audit_service import audit_service




class WebhookService:
    def verify_signature(self, raw_body: bytes, signature: str) -> bool:
        """
        Verifies Razorpay HMAC-SHA256 signature against secret.
        """
        if not signature:
            raise HTTPException(status_code=401, detail="Missing X-Razorpay-Signature header")

        secret_bytes = settings.RAZORPAY_WEBHOOK_SECRET.encode("utf-8")
        expected_sig = hmac.new(secret_bytes, raw_body, hashlib.sha256).hexdigest()

        if not hmac.compare_digest(expected_sig, signature):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

        return True

    def process_razorpay_webhook(
        self,
        db: Session,
        payload_data: Dict[str, Any],
        raw_body: bytes = None,
        signature: str = None,
        verify_sig: bool = True
    ) -> Dict[str, Any]:
        """
        Idempotent payment webhook ingestion pipeline.
        Parses payload, verifies signature & idempotency, persists Payment & Customer,
        executes ML diagnosis & prediction, ranks RecoveryCase, and triggers Agent evaluation.
        """
        # Step 1: Optional Signature Verification
        if verify_sig and raw_body and signature:
            self.verify_signature(raw_body, signature)

        event_id = payload_data.get("event_id")
        event_type = payload_data.get("event")

        if not event_id or not event_type:
            raise HTTPException(status_code=400, detail="Missing event_id or event in webhook payload")

        # Step 2: Persistent Idempotency Check
        existing_event = (
            db.query(WebhookEvent)
            .filter(WebhookEvent.gateway == "razorpay", WebhookEvent.event_id == event_id)
            .first()
        )
        if existing_event:
            audit_service.record_event(
                db,
                event_type="WEBHOOK_DUPLICATE",
                actor_type="GATEWAY",
                description=f"Duplicate Razorpay webhook event_id '{event_id}' safely ignored by idempotency filter",
                metadata={"event_id": event_id, "event_type": event_type}
            )
            return {
                "status": "idempotent_ignored",
                "message": "Duplicate event_id already processed",
                "event_id": event_id,
                "event_type": event_type
            }

        # Step 3: Event Type Routing
        if event_type != "payment.failed":
            # Record ignored event in DB for audit trail
            web_evt = WebhookEvent(
                event_id=event_id,
                event_type=event_type,
                gateway="razorpay",
                status="IGNORED"
            )
            db.add(web_evt)
            db.commit()

            audit_service.record_event(
                db,
                event_type="WEBHOOK_IGNORED",
                actor_type="GATEWAY",
                description=f"Ignored non-failure Razorpay webhook event type '{event_type}'",
                metadata={"event_id": event_id, "event": event_type}
            )
            return {
                "status": "ignored",
                "reason": "unsupported_event_type",
                "event": event_type,
                "event_id": event_id
            }

        # Step 4: Parse Payment Payload
        payload_obj = payload_data.get("payload", {})
        payment_info = payload_obj.get("payment", {})
        customer_info = payload_obj.get("customer", {})

        raw_amount = payment_info.get("amount", 14900)
        # Handle paise conversion if amount is integer > 1000 without decimal
        if isinstance(raw_amount, int) and raw_amount >= 100:
            amount_usd = round(raw_amount / 100.0, 2)
        else:
            amount_usd = round(float(raw_amount), 2)

        currency = payment_info.get("currency", "INR")
        gateway_payment_id = payment_info.get("id", f"pay_sim_{random.randint(10000, 99999)}")
        error_code = payment_info.get("error_code", "BAD_REQUEST_ERROR")
        error_desc = payment_info.get("error_description", "Payment failed")
        method = payment_info.get("method", "card")

        # Normalize failure reason & category
        fail_reason, fail_cat = self._normalize_failure(error_code, error_desc)

        # Step 5: Customer Lookup or Creation
        ext_cust_id = customer_info.get("id", f"cust_sim_{gateway_payment_id[-5:]}")
        customer = (
            db.query(Customer)
            .filter(Customer.external_customer_id == ext_cust_id)
            .first()
        )
        if not customer:
            customer = Customer(
                external_customer_id=ext_cust_id,
                name=f"Razorpay Customer ({ext_cust_id})",
                email=f"{ext_cust_id.lower()}@example.com",
                customer_since=datetime.now(timezone.utc),
                lifetime_value=round(random.uniform(300.0, 2500.0), 2),
                opted_out=False
            )
            db.add(customer)
            db.flush()

        # Step 6: Payment Persistence
        payment = Payment(
            gateway_payment_id=gateway_payment_id,
            customer_id=customer.id,
            amount=amount_usd,
            currency=currency,
            status="FAILED",
            failure_reason=fail_reason,
            failure_category=fail_cat,
            attempt_number=1
        )
        db.add(payment)
        db.flush()

        # Step 7: Execute ML Models (Root Cause Diagnosis & Recovery Probability)
        cause, conf = predictor.predict_root_cause(
            payment_amount=amount_usd,
            failure_reason=fail_reason,
            failure_category=fail_cat,
            attempt_number=1
        )

        prob = predictor.predict_recovery_probability(
            payment_amount=amount_usd,
            failure_category=fail_cat,
            customer_ltv=customer.lifetime_value,
            customer_tenure=12,
            attempt_number=1,
            previous_failures=0,
            days_since_last_payment=30,
            historical_success_rate=0.85,
            monthly_charge=50.0,
            payment_method=method,
            gateway_response_code=error_code
        )

        exp_recovery = round(amount_usd * prob, 2)
        priority_score = exp_recovery

        # Step 8: Create RecoveryCase Record
        case = RecoveryCase(
            payment_id=payment.id,
            customer_id=customer.id,
            status="OPEN",
            revenue_at_risk=amount_usd,
            recovery_probability=prob,
            expected_recovery=exp_recovery,
            priority_score=priority_score,
            root_cause=cause,
            root_cause_confidence=conf,
            retry_count=0,
            created_at=datetime.now(timezone.utc)
        )

        # Step 9: Recovery Agent Evaluation & Workflow Routing
        rec_action, agent_reason, agent_conf = recovery_agent.evaluate_case(db, case)
        case.recommended_action = rec_action
        case.agent_confidence = agent_conf

        is_cust_req, act_type, act_desc = policy_engine.classify_customer_action_requirement(fail_reason, cause)
        if is_cust_req:
            policy = policy_engine.get_active_policy(db)
            now = datetime.now(timezone.utc)
            case.status = "CUSTOMER_ACTION_REQUIRED"
            case.customer_action_required = True
            case.customer_action_type = act_type
            case.customer_action_status = "PENDING"
            case.customer_action_description = act_desc
            case.waiting_since = now
            case.retry_after = now + timedelta(hours=policy.customer_action_wait_hours)
            case.expires_at = now + timedelta(hours=policy.customer_action_expire_hours)
            case.next_action = "WAIT_FOR_CUSTOMER_ACTION"
        elif rec_action == "HUMAN_REVIEW":
            case.status = "ESCALATED"
            case.next_action = "HUMAN_REVIEW"
        elif rec_action == "STOP":
            case.status = "STOPPED"
            case.next_action = "NONE"
        else:
            case.status = "PRIORITIZED"
            case.next_action = rec_action

        db.add(case)
        db.flush()


        # Step 10: Persist Webhook Event for Idempotency Tracking
        web_evt = WebhookEvent(
            event_id=event_id,
            event_type=event_type,
            gateway="razorpay",
            status="PROCESSED"
        )
        db.add(web_evt)
        db.commit()

        # Step 11: Audit Trail Record Creation
        audit_service.record_event(
            db,
            event_type="WEBHOOK_RECEIVED",
            actor_type="GATEWAY",
            description=f"Received valid Razorpay webhook event '{event_id}' ({event_type})",
            case_id=case.id,
            metadata={"event_id": event_id, "amount": amount_usd, "gateway_payment_id": gateway_payment_id}
        )
        audit_service.record_event(
            db,
            event_type="PAYMENT_INGESTED",
            actor_type="GATEWAY",
            description=f"Ingested failed payment {gateway_payment_id} for ${amount_usd:,.2f} ({fail_reason})",
            case_id=case.id
        )
        audit_service.record_event(
            db,
            event_type="RECOVERY_CASE_CREATED",
            actor_type="SYSTEM",
            description=f"Initialized prioritized recovery case. P(Recovery)={prob*100:.0f}%, Expected=${exp_recovery:,.2f}",
            case_id=case.id
        )

        return {
            "status": "success",
            "message": "Payment failure webhook ingested and recovery case initialized",
            "event_id": event_id,
            "payment_id": payment.id,
            "case_id": case.id,
            "customer_name": customer.name,
            "amount": amount_usd,
            "failure_reason": fail_reason,
            "root_cause": cause,
            "recovery_probability": prob,
            "expected_recovery": exp_recovery,
            "recommended_action": rec_action
        }

    def _normalize_failure(self, error_code: str, error_desc: str) -> Tuple[str, str]:
        code_str = str(error_code or error_desc).upper()
        if "TIMEOUT" in code_str or "NETWORK" in code_str or "SERVER" in code_str:
            return "NETWORK_TIMEOUT", "TRANSIENT_FAILURE"
        elif "GATEWAY" in code_str or "BANK" in code_str or "SYSTEM" in code_str:
            return "GATEWAY_ERROR", "TRANSIENT_FAILURE"
        elif "INSUFFICIENT" in code_str or "FUNDS" in code_str:
            return "INSUFFICIENT_FUNDS", "CUSTOMER_ACTION"
        elif "EXPIRED" in code_str:
            return "CARD_EXPIRED", "CUSTOMER_ACTION"
        elif "FRAUD" in code_str or "RISK" in code_str or "SUSPICIOUS" in code_str:
            return "FRAUD_RISK", "RISK_RELATED"
        elif "CLOSED" in code_str:
            return "ACCOUNT_CLOSED", "RISK_RELATED"
        else:
            return "CARD_DECLINED", "CUSTOMER_ACTION"


webhook_service = WebhookService()
