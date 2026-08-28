import json
from datetime import datetime, timezone
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
        recipient: str = None
    ) -> Notification:
        if not recipient and customer_id:
            cust = db.query(Customer).filter(Customer.id == customer_id).first()
            if cust:
                recipient = cust.email or cust.phone or "customer@example.com"
        
        notification = Notification(
            case_id=case_id,
            customer_id=customer_id,
            type=type_,
            channel=channel,
            status="DELIVERED",
            recipient=recipient or "ops-team@recoverai.com",
            sent_at=datetime.now(timezone.utc),
            delivered_at=datetime.now(timezone.utc)
        )
        db.add(notification)
        db.commit()
        db.refresh(notification)
        return notification

notification_service = NotificationService()
