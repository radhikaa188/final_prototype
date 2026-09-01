from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import Notification, Customer, User
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def list_notifications(
    limit: int = Query(50),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Notification)
    total = query.count()
    unread_count = query.filter(Notification.clicked_at.is_(None)).count()
    notifications = query.order_by(Notification.sent_at.desc()).offset(offset).limit(limit).all()

    res = []
    for n in notifications:
        cust = db.query(Customer).filter(Customer.id == n.customer_id).first() if n.customer_id else None
        res.append({
            "id": n.id,
            "case_id": n.case_id,
            "customer_id": n.customer_id,
            "customer_name": cust.name if cust else "System User",
            "type": n.type,
            "channel": n.channel,
            "status": n.status,
            "recipient": n.recipient,
            "sent_at": n.sent_at.isoformat() if n.sent_at else None,
            "delivered_at": n.delivered_at.isoformat() if n.delivered_at else None,
            "clicked_at": n.clicked_at.isoformat() if n.clicked_at else None,
            "is_read": n.clicked_at is not None
        })

    return {
        "total": total,
        "unread_count": unread_count,
        "notifications": res
    }


@router.post("/{notification_id}/read")
def mark_notification_read(
    notification_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    notif = db.query(Notification).filter(Notification.id == notification_id).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")

    if not notif.clicked_at:
        notif.clicked_at = datetime.now(timezone.utc)
        notif.status = "CLICKED"
        db.commit()

    return {"status": "success", "id": notif.id, "is_read": True}


@router.post("/mark-all-read")
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    now = datetime.now(timezone.utc)
    updated = (
        db.query(Notification)
        .filter(Notification.clicked_at.is_(None))
        .update({"clicked_at": now, "status": "CLICKED"}, synchronize_session=False)
    )
    db.commit()
    return {"status": "success", "marked_read_count": updated}
