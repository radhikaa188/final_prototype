from datetime import datetime, timezone
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import RecoveryCase, Payment, Customer, AgentRun, AgentRunStep, RecoveryAction, AuditEvent
from app.ml.predictor import predictor
from app.agents.recovery_agent import recovery_agent
from app.policies.guardrails import policy_engine
from app.services.audit_service import audit_service
from app.services.execution_service import execution_service

router = APIRouter(prefix="/recovery-cases", tags=["recovery-cases"])

@router.get("")
def list_recovery_cases(
    status: str = Query(None),
    recommended_action: str = Query(None),
    root_cause: str = Query(None),
    min_amount: float = Query(None),
    limit: int = Query(100),
    offset: int = Query(0),
    db: Session = Depends(get_db)
):
    query = db.query(RecoveryCase)

    if status:
        if status == "HIGH_PRIORITY":
            query = query.filter(RecoveryCase.priority_score >= 50.0)
        elif status == "NEEDS_REVIEW":
            query = query.filter(RecoveryCase.status == "ESCALATED")
        elif status == "BLOCKED":
            query = query.filter(RecoveryCase.status == "STOPPED")
        elif status == "RETRY_READY":
            query = query.filter(RecoveryCase.recommended_action == "RETRY", RecoveryCase.status != "RECOVERED")
        else:
            query = query.filter(RecoveryCase.status == status)

    if recommended_action:
        query = query.filter(RecoveryCase.recommended_action == recommended_action)

    if root_cause:
        query = query.filter(RecoveryCase.root_cause == root_cause)

    if min_amount:
        query = query.filter(RecoveryCase.revenue_at_risk >= min_amount)

    total = query.count()
    # Rank strictly by priority_score (Expected Recoverable Revenue)
    cases = query.order_by(RecoveryCase.priority_score.desc()).offset(offset).limit(limit).all()

    res = []
    for rank, case in enumerate(cases, start=offset + 1):
        payment = db.query(Payment).filter(Payment.id == case.payment_id).first()
        customer = db.query(Customer).filter(Customer.id == case.customer_id).first()
        res.append({
            "priority": rank,
            "id": case.id,
            "payment_id": payment.id if payment else case.payment_id,
            "gateway_payment_id": payment.gateway_payment_id if payment else case.payment_id,
            "customer_id": case.customer_id,
            "customer_name": customer.name if customer else "Unknown Customer",
            "amount": case.revenue_at_risk,
            "failure_reason": payment.failure_reason if payment else "Unknown",
            "recovery_probability": case.recovery_probability,
            "expected_recovery": case.expected_recovery,
            "priority_score": case.priority_score,
            "root_cause": case.root_cause,
            "recommended_action": case.recommended_action,
            "status": case.status,
            "retry_count": case.retry_count,
            "created_at": case.created_at.isoformat() if case.created_at else None
        })

    return {"total": total, "cases": res}

@router.get("/{case_id}")
def get_case_detail(case_id: str, db: Session = Depends(get_db)):
    case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Recovery case not found")

    payment = db.query(Payment).filter(Payment.id == case.payment_id).first()
    customer = db.query(Customer).filter(Customer.id == case.customer_id).first()
    actions = db.query(RecoveryAction).filter(RecoveryAction.case_id == case.id).order_by(RecoveryAction.executed_at.desc()).all()
    events = db.query(AuditEvent).filter(AuditEvent.case_id == case.id).order_by(AuditEvent.created_at.desc()).all()
    runs = db.query(AgentRun).filter(AgentRun.case_id == case.id).order_by(AgentRun.started_at.desc()).all()

    # Dynamic guardrail evaluation for display
    action = case.recommended_action or "RETRY"
    guardrail_allowed, guardrail_reason, guardrail_checks = policy_engine.validate_action(db, case, action)

    # Historical metrics for customer
    cust_successful_pay = db.query(Payment).filter(Payment.customer_id == customer.id, Payment.status == "SUCCESS").count() if customer else 0
    cust_failed_pay = db.query(Payment).filter(Payment.customer_id == customer.id, Payment.status == "FAILED").count() if customer else 0

    return {
        "id": case.id,
        "status": case.status,
        "payment": {
            "id": payment.id if payment else None,
            "gateway_payment_id": payment.gateway_payment_id if payment else None,
            "amount": payment.amount if payment else case.revenue_at_risk,
            "currency": payment.currency if payment else "USD",
            "status": payment.status if payment else "FAILED",
            "failure_reason": payment.failure_reason if payment else None,
            "failure_category": payment.failure_category if payment else None,
            "attempt_number": payment.attempt_number if payment else 1,
            "created_at": payment.created_at.isoformat() if payment and payment.created_at else None
        },
        "customer": {
            "id": customer.id if customer else None,
            "name": customer.name if customer else "Unknown",
            "email": customer.email if customer else None,
            "phone": customer.phone if customer else None,
            "customer_since": customer.customer_since.isoformat() if customer and customer.customer_since else None,
            "lifetime_value": customer.lifetime_value if customer else 0.0,
            "opted_out": customer.opted_out if customer else False,
            "successful_payments": cust_successful_pay,
            "failed_payments": cust_failed_pay
        },
        "ml_intelligence": {
            "root_cause": case.root_cause,
            "root_cause_confidence": case.root_cause_confidence,
            "recovery_probability": case.recovery_probability,
            "expected_recovery": case.expected_recovery,
            "priority_score": case.priority_score
        },
        "agent_decision": {
            "recommended_action": case.recommended_action,
            "reason": f"Failure diagnosed as {case.root_cause or 'TRANSIENT_FAILURE'}. P(Recovery) is {((case.recovery_probability or 0.5)*100):.0f}%. Retry count is {case.retry_count}.",
            "confidence": case.agent_confidence
        },
        "guardrail_result": {
            "allowed": guardrail_allowed,
            "reason": guardrail_reason,
            "checks": guardrail_checks
        },
        "retry_count": case.retry_count,
        "actions_history": [
            {
                "id": a.id,
                "action_type": a.action_type,
                "status": a.status,
                "reason": a.reason,
                "executed_at": a.executed_at.isoformat() if a.executed_at else None,
                "amount_recovered": a.amount_recovered
            } for a in actions
        ],
        "timeline": [
            {
                "id": e.id,
                "timestamp": e.created_at.isoformat() if e.created_at else None,
                "actor": e.actor_type,
                "event": e.event_type,
                "description": e.description
            } for e in events
        ],
        "latest_run_id": runs[0].id if runs else None
    }

@router.post("/{case_id}/approve")
def approve_recovery_case(case_id: str, db: Session = Depends(get_db)):
    case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Create agent_run
    agent_run = AgentRun(
        case_id=case.id,
        status="PENDING",
        trigger_type="MANUAL_APPROVE",
        recommended_action=case.recommended_action or "RETRY",
        approved=True,
        approved_by="OPS_USER"
    )
    db.add(agent_run)
    case.status = "APPROVED"
    db.commit()
    db.refresh(agent_run)

    audit_service.record_event(db, "CASE_APPROVED", "HUMAN", f"User approved recommended action: {case.recommended_action}", case_id=case.id, agent_run_id=agent_run.id)

    return {"run_id": agent_run.id, "case_id": case.id, "status": "APPROVED"}

@router.post("/{case_id}/execute")
def execute_recovery_case(case_id: str, db: Session = Depends(get_db)):
    case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    agent_run = AgentRun(
        case_id=case.id,
        status="PENDING",
        trigger_type="MANUAL_EXECUTE",
        recommended_action=case.recommended_action or "RETRY",
        approved=True,
        approved_by="OPS_USER"
    )
    db.add(agent_run)
    case.status = "EXECUTING"
    db.commit()
    db.refresh(agent_run)

    audit_service.record_event(db, "DIRECT_EXECUTION_TRIGGERED", "HUMAN", f"User manually triggered execution of action: {case.recommended_action}", case_id=case.id, agent_run_id=agent_run.id)

    return {"run_id": agent_run.id, "case_id": case.id, "status": "EXECUTING"}

@router.post("/{case_id}/reject")
def reject_recovery_case(case_id: str, db: Session = Depends(get_db)):
    case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    case.status = "STOPPED"
    case.next_action = "NONE"
    db.commit()

    audit_service.record_event(db, "CASE_REJECTED", "HUMAN", "User rejected recovery action. Recovery stopped.", case_id=case.id)

    return {"case_id": case.id, "status": "STOPPED"}

@router.post("/{case_id}/escalate")
def escalate_recovery_case(case_id: str, db: Session = Depends(get_db)):
    case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    case.status = "ESCALATED"
    case.next_action = "HUMAN_REVIEW"
    db.commit()

    audit_service.record_event(db, "CASE_ESCALATED", "HUMAN", "User escalated case for senior human review.", case_id=case.id)

    return {"case_id": case.id, "status": "ESCALATED"}
