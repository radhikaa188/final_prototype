from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import Notification, Customer

router = APIRouter(prefix="/notifications", tags=["notifications"])

@router.get("")
def list_notifications(
    limit: int = Query(50),
    offset: int = Query(0),
    db: Session = Depends(get_db)
):
    query = db.query(Notification)
    total = query.count()
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
            "clicked_at": n.clicked_at.isoformat() if n.clicked_at else None
        })

    return {"total": total, "notifications": res}
