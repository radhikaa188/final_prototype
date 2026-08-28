import json
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import AuditEvent

router = APIRouter(prefix="/audit", tags=["audit"])

@router.get("")
def list_audit_events(
    actor_type: str = Query(None),
    event_type: str = Query(None),
    case_id: str = Query(None),
    limit: int = Query(100),
    offset: int = Query(0),
    db: Session = Depends(get_db)
):
    query = db.query(AuditEvent)
    if actor_type:
        query = query.filter(AuditEvent.actor_type == actor_type)
    if event_type:
        query = query.filter(AuditEvent.event_type == event_type)
    if case_id:
        query = query.filter(AuditEvent.case_id == case_id)

    total = query.count()
    events = query.order_by(AuditEvent.created_at.desc()).offset(offset).limit(limit).all()

    res = []
    for e in events:
        res.append({
            "id": e.id,
            "timestamp": e.created_at.isoformat() if e.created_at else None,
            "case_id": e.case_id,
            "agent_run_id": e.agent_run_id,
            "actor_type": e.actor_type,
            "event_type": e.event_type,
            "description": e.description,
            "metadata": json.loads(e.metadata_json) if e.metadata_json else None
        })

    return {"total": total, "events": res}
