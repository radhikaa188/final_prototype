from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.session import get_db
from app.db.models import Payment, RecoveryCase, RecoveryAction, AgentRun, AuditEvent

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

@router.get("/summary")
def get_dashboard_summary(db: Session = Depends(get_db)):
    # Revenue at Risk = sum of failed payment amounts
    revenue_at_risk = db.query(func.sum(RecoveryCase.revenue_at_risk)).scalar() or 0.0
    
    # Recoverable Revenue = sum of expected_recovery across open/prioritized/executing cases
    recoverable_revenue = db.query(func.sum(RecoveryCase.expected_recovery)).filter(
        RecoveryCase.status.in_(["OPEN", "DIAGNOSED", "PRIORITIZED", "ACTION_PROPOSED", "AWAITING_APPROVAL", "APPROVED", "EXECUTING", "RE_EVALUATING"])
    ).scalar() or 0.0

    # Revenue Recovered = sum of amount_recovered where action status is SUCCESS
    revenue_recovered = db.query(func.sum(RecoveryAction.amount_recovered)).filter(
        RecoveryAction.status == "SUCCESS"
    ).scalar() or 0.0

    # Recovery Rate = recovered / revenue_at_risk
    recovery_rate = (revenue_recovered / revenue_at_risk) if revenue_at_risk > 0 else 0.0

    # Active Recovery Cases count
    active_cases = db.query(RecoveryCase).filter(
        RecoveryCase.status.in_(["OPEN", "DIAGNOSED", "PRIORITIZED", "ACTION_PROPOSED", "AWAITING_APPROVAL", "APPROVED", "EXECUTING", "RE_EVALUATING", "ESCALATED"])
    ).count()

    total_cases = db.query(RecoveryCase).count()

    return {
        "revenue_at_risk": round(revenue_at_risk, 2),
        "recoverable_revenue": round(recoverable_revenue, 2),
        "revenue_recovered": round(revenue_recovered, 2),
        "recovery_rate": round(recovery_rate, 4),
        "active_cases": active_cases,
        "total_cases": total_cases
    }

@router.get("/revenue")
def get_revenue_timeline(db: Session = Depends(get_db)):
    # Aggregated breakdown by date
    cases = db.query(RecoveryCase).all()
    # Group by date string (YYYY-MM-DD)
    date_map = {}
    for case in cases:
        date_str = case.created_at.strftime("%Y-%m-%d") if case.created_at else "2026-05-01"
        if date_str not in date_map:
            date_map[date_str] = {"date": date_str, "at_risk": 0.0, "recoverable": 0.0, "recovered": 0.0}
        date_map[date_str]["at_risk"] += case.revenue_at_risk
        date_map[date_str]["recoverable"] += case.expected_recovery

    # Add recovered actions
    actions = db.query(RecoveryAction).filter(RecoveryAction.status == "SUCCESS").all()
    for act in actions:
        date_str = act.executed_at.strftime("%Y-%m-%d") if act.executed_at else "2026-05-01"
        if date_str in date_map:
            date_map[date_str]["recovered"] += act.amount_recovered

    sorted_timeline = sorted(date_map.values(), key=lambda x: x["date"])
    
    # Format currency for chart
    for item in sorted_timeline:
        item["at_risk"] = round(item["at_risk"], 2)
        item["recoverable"] = round(item["recoverable"], 2)
        item["recovered"] = round(item["recovered"], 2)

    return sorted_timeline

@router.get("/funnel")
def get_dashboard_funnel(db: Session = Depends(get_db)):
    total_failed = db.query(Payment).filter(Payment.status == "FAILED").count()
    total_cases = db.query(RecoveryCase).count()
    eligible = db.query(RecoveryCase).filter(RecoveryCase.status != "STOPPED").count()
    actioned = db.query(RecoveryAction).count()
    recovered = db.query(RecoveryCase).filter(RecoveryCase.status == "RECOVERED").count()

    return [
        {"stage": "Failed Payments", "count": total_failed, "color": "#ef4444"},
        {"stage": "Recovery Cases", "count": total_cases, "color": "#f59e0b"},
        {"stage": "Eligible Cases", "count": eligible, "color": "#3b82f6"},
        {"stage": "Actions Executed", "count": actioned, "color": "#8b5cf6"},
        {"stage": "Revenue Recovered", "count": recovered, "color": "#10b981"}
    ]

@router.get("/activity")
def get_dashboard_activity(db: Session = Depends(get_db)):
    events = db.query(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(10).all()
    res = []
    for ev in events:
        res.append({
            "id": ev.id,
            "timestamp": ev.created_at.isoformat() if ev.created_at else None,
            "case_id": ev.case_id,
            "actor_type": ev.actor_type,
            "event_type": ev.event_type,
            "description": ev.description
        })
    return res
