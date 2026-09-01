from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from app.db.models import Notification, Customer

class NotificationService:
    @staticmethod
    def send_notification(
        db: Session,
        case_id: str,
        customer_id: str,
        type_: str,
        channel: str = "EMAIL",
        recipient: str = None,
        status: str = "SENT",
        reason: str = None,
        agent_run_id: str = None,
        deduplicate_seconds: int = 15
    ) -> Notification:
        # Check deduplication window to prevent rapid duplicate notifications on polling/clicks
        if case_id and deduplicate_seconds > 0:
            cutoff = datetime.now(timezone.utc) - timedelta(seconds=deduplicate_seconds)
            existing = (
                db.query(Notification)
                .filter(
                    Notification.case_id == case_id,
                    Notification.type == type_,
                    Notification.sent_at >= cutoff
                )
                .first()
            )
            if existing:
                return existing

        cust = db.query(Customer).filter(Customer.id == customer_id).first() if customer_id else None
        
        # Enforce customer opt-out policy for automated customer-facing communications
        if cust and cust.opted_out and type_ in ["CUSTOMER_NUDGE", "NUDGE_SENT", "AUTOMATIC_RETRY_ATTEMPTED", "CUSTOMER_ACTION_REQUIRED"]:
            status = "BLOCKED"
            reason = "Customer opted out of automatic recovery communications"

        if not recipient:
            if cust:
                recipient = cust.email or cust.phone or "customer@example.com"
            else:
                recipient = "operations@revora.ai" if "HUMAN" in type_ or "POLICY" in type_ else "customer@example.com"

        notification = Notification(
            case_id=case_id,
            customer_id=customer_id,
            type=type_,
            channel=channel,
            status=status,
            recipient=recipient,
            sent_at=datetime.now(timezone.utc),
            delivered_at=datetime.now(timezone.utc) if status in ["SENT", "DELIVERED"] else None
        )
        db.add(notification)
        db.flush()

        # Record audit event for every notification
        audit_desc = f"Notification ({type_}) {status} to {recipient}"
        if reason:
            audit_desc += f" (Reason: {reason})"

        from app.services.audit_service import audit_service
        audit_service.record_event(
            db,
            "NOTIFICATION_DISPATCHED" if status != "BLOCKED" else "NOTIFICATION_BLOCKED",
            "SYSTEM",
            audit_desc,
            case_id=case_id,
            agent_run_id=agent_run_id
        )

        db.commit()
        db.refresh(notification)
        return notification

notification_service = NotificationService()
