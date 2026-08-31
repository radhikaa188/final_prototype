import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import AgentRun, AgentRunStep, RecoveryCase, Payment, Customer, User
from app.auth.dependencies import get_current_user
from app.services.execution_service import execution_service

router = APIRouter(prefix="/agent", tags=["agent"])

@router.get("/runs")
def list_agent_runs(
    status: str = Query(None),
    limit: int = Query(50),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(AgentRun)
    if status:
        query = query.filter(AgentRun.status == status)

    total = query.count()
    runs = query.order_by(AgentRun.started_at.desc()).offset(offset).limit(limit).all()

    res = []
    for r in runs:
        case = db.query(RecoveryCase).filter(RecoveryCase.id == r.case_id).first()
        payment = db.query(Payment).filter(Payment.id == case.payment_id).first() if case else None
        res.append({
            "id": r.id,
            "case_id": r.case_id,
            "amount": case.revenue_at_risk if case else 0.0,
            "status": r.status,
            "trigger_type": r.trigger_type,
            "agent_version": r.agent_version,
            "recommended_action": r.recommended_action,
            "approved": r.approved,
            "final_result": r.final_result,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "error": r.error
        })

    return {"total": total, "runs": res}

@router.get("/runs/{run_id}")
def get_agent_run(run_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    r = db.query(AgentRun).filter(AgentRun.id == run_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Agent run not found")

    case = db.query(RecoveryCase).filter(RecoveryCase.id == r.case_id).first()
    payment = db.query(Payment).filter(Payment.id == case.payment_id).first() if case else None
    customer = db.query(Customer).filter(Customer.id == case.customer_id).first() if case else None
    steps = db.query(AgentRunStep).filter(AgentRunStep.run_id == r.id).order_by(AgentRunStep.step_number.asc()).all()

    steps_res = []
    for s in steps:
        steps_res.append({
            "id": s.id,
            "step_number": s.step_number,
            "step_name": s.step_name,
            "status": s.status,
            "input_summary": s.input_summary,
            "output_summary": s.output_summary,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "completed_at": s.completed_at.isoformat() if s.completed_at else None,
            "error": s.error
        })

    return {
        "id": r.id,
        "case_id": r.case_id,
        "payment": {
            "id": payment.id if payment else None,
            "gateway_payment_id": payment.gateway_payment_id if payment else None,
            "amount": payment.amount if payment else (case.revenue_at_risk if case else 0.0),
            "status": payment.status if payment else "FAILED"
        },
        "customer_name": customer.name if customer else "Unknown",
        "status": r.status,
        "trigger_type": r.trigger_type,
        "agent_version": r.agent_version,
        "recommended_action": r.recommended_action,
        "approved": r.approved,
        "final_result": r.final_result,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        "error": r.error,
        "steps": steps_res
    }

@router.get("/runs/{run_id}/stream")
def stream_agent_run(run_id: str):
    """Server-Sent Events endpoint streaming real execution steps to frontend"""
    return EventSourceResponse(execution_service.stream_agent_steps(run_id))
