from datetime import datetime, timezone, timedelta
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import RecoveryCase, Payment, Customer, AgentRun, AgentRunStep, RecoveryAction, AuditEvent, User
from app.auth.dependencies import get_current_user, require_role
from app.ml.predictor import predictor
from app.ml.action_predictor import action_predictor
from app.agents.recovery_agent import recovery_agent
from app.policies.guardrails import policy_engine
from app.services.audit_service import audit_service
from app.services.execution_service import execution_service
from app.services.explainability_service import explainability_service

router = APIRouter(prefix="/recovery-cases", tags=["recovery-cases"])

@router.get("")
def list_recovery_cases(
    status: str = Query(None),
    recommended_action: str = Query(None),
    root_cause: str = Query(None),
    min_amount: float = Query(None),
    limit: int = Query(100),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
def get_case_detail(case_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Recovery case not found")

    payment = db.query(Payment).filter(Payment.id == case.payment_id).first()
    customer = db.query(Customer).filter(Customer.id == case.customer_id).first()
    actions = db.query(RecoveryAction).filter(RecoveryAction.case_id == case.id).order_by(RecoveryAction.executed_at.asc()).all()
    events = db.query(AuditEvent).filter(AuditEvent.case_id == case.id).order_by(AuditEvent.created_at.asc()).all()
    runs = db.query(AgentRun).filter(AgentRun.case_id == case.id).order_by(AgentRun.started_at.asc()).all()

    # Dynamic guardrail evaluation for display
    action = case.recommended_action or "RETRY"
    guardrail_allowed, guardrail_reason, guardrail_checks = policy_engine.validate_action(db, case, action)

    # Historical metrics for customer
    cust_successful_pay = db.query(Payment).filter(Payment.customer_id == customer.id, Payment.status == "SUCCESS").count() if customer else 0
    cust_failed_pay = db.query(Payment).filter(Payment.customer_id == customer.id, Payment.status == "FAILED").count() if customer else 0

    eval_res = recovery_agent.evaluate_case_full(db, case)
    probabilities = eval_res.get("probabilities", {})

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
            "priority_score": case.priority_score,
            "probabilities": probabilities
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
        "customer_action_info": {
            "required": case.customer_action_required,
            "type": case.customer_action_type,
            "description": case.customer_action_description,
            "status": case.customer_action_status,
            "notified_at": case.customer_notified_at.isoformat() if case.customer_notified_at else None,
            "waiting_since": case.waiting_since.isoformat() if case.waiting_since else None,
            "retry_after": case.retry_after.isoformat() if case.retry_after else None,
            "expires_at": case.expires_at.isoformat() if case.expires_at else None,
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
        "latest_run_id": runs[0].id if runs else None,
        "explainability": explainability_service.explain_decision(
            case=case,
            payment=payment,
            customer=customer,
            probabilities=probabilities,
            guardrail_result={
                "allowed": guardrail_allowed,
                "reason": guardrail_reason,
                "checks": guardrail_checks
            }
        )
    }

@router.post("/{case_id}/approve")
def approve_recovery_case(case_id: str, payload: dict = None, db: Session = Depends(get_db), current_user: User = Depends(require_role(["OPS", "ADMIN"]))):
    case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    payment = db.query(Payment).filter(Payment.id == case.payment_id).first()
    if case.status == "RECOVERED" or (payment and payment.status == "SUCCESS"):
        raise HTTPException(status_code=400, detail="Case already resolved as RECOVERED — cannot perform action")

    # Get approved action
    action = (payload or {}).get("action") or case.recommended_action or "RETRY"
    if action not in ("RETRY", "CUSTOMER_NUDGE"):
        raise HTTPException(status_code=400, detail=f"Action '{action}' is not supported for manual human approval.")

    operator_label = f"{current_user.name or current_user.email} ({current_user.role})"

    # Create agent_run
    agent_run = AgentRun(
        case_id=case.id,
        status="PENDING",
        trigger_type="MANUAL_APPROVE",
        recommended_action=action,
        approved=True,
        approved_by=operator_label
    )
    db.add(agent_run)
    case.status = "APPROVED"
    db.commit()
    db.refresh(agent_run)

    # Record HUMAN_APPROVAL audit event with authenticated operator identity
    audit_service.record_event(
        db, 
        "HUMAN_APPROVAL", 
        "HUMAN", 
        f"Employee ({operator_label}) approved recovery action: {action}", 
        case_id=case.id, 
        agent_run_id=agent_run.id
    )
    db.commit()

    # Execute workflow synchronously
    execution_service.run_agent_workflow_sync(agent_run.id)
    db.refresh(case)
    db.refresh(agent_run)
    db.refresh(payment)

    # Calculate amount_recovered from recovery actions
    recovered_amount = 0.0
    if payment.status == "SUCCESS":
        # Find the successful recovery action
        action_rec = db.query(RecoveryAction).filter(
            RecoveryAction.case_id == case.id, 
            RecoveryAction.status == "SUCCESS"
        ).order_by(RecoveryAction.executed_at.desc()).first()
        if action_rec:
            recovered_amount = action_rec.amount_recovered or payment.amount

    return {
        "run_id": agent_run.id,
        "run_status": agent_run.status,
        "final_result": agent_run.final_result or agent_run.status,
        "case_status": case.status,
        "payment_status": payment.status,
        "approved_action": action,
        "amount_recovered": recovered_amount
    }

@router.post("/{case_id}/execute")
def execute_recovery_case(case_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_role(["OPS", "ADMIN"]))):
    case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if case.status == "RECOVERED":
        raise HTTPException(status_code=400, detail="Case already recovered — cannot re-execute")

    operator_label = f"{current_user.name or current_user.email} ({current_user.role})"

    agent_run = AgentRun(
        case_id=case.id,
        status="PENDING",
        trigger_type="MANUAL_EXECUTE",
        recommended_action=case.recommended_action or "RETRY",
        approved=True,
        approved_by=operator_label
    )
    db.add(agent_run)
    case.status = "EXECUTING"
    db.commit()
    db.refresh(agent_run)

    audit_service.record_event(db, "DIRECT_EXECUTION_TRIGGERED", "HUMAN", f"Employee ({operator_label}) manually triggered execution of action: {case.recommended_action}", case_id=case.id, agent_run_id=agent_run.id)

    return {"run_id": agent_run.id, "case_id": case.id, "status": "EXECUTING"}

@router.post("/{case_id}/reject")
def reject_recovery_case(case_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_role(["OPS", "ADMIN"]))):
    case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    operator_label = f"{current_user.name or current_user.email} ({current_user.role})"

    case.status = "STOPPED"
    case.next_action = "NONE"
    db.commit()

    audit_service.record_event(db, "HUMAN_REJECTION", "HUMAN", f"Employee ({operator_label}) rejected recovery action. Recovery stopped.", case_id=case.id)

    return {"case_id": case.id, "status": "STOPPED"}

@router.post("/{case_id}/escalate")
def escalate_recovery_case(case_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_role(["OPS", "ADMIN"]))):
    case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if case.status == "RECOVERED":
        raise HTTPException(status_code=400, detail="Case already recovered — cannot re-execute")

    operator_label = f"{current_user.name or current_user.email} ({current_user.role})"

    case.status = "ESCALATED"
    case.next_action = "HUMAN_REVIEW"
    db.commit()

    audit_service.record_event(db, "CASE_ESCALATED", "HUMAN", f"Employee ({operator_label}) escalated case for senior human review.", case_id=case.id)

    return {"case_id": case.id, "status": "ESCALATED"}

@router.post("/{case_id}/customer-action")
def complete_customer_action(case_id: str, payload: dict = None, db: Session = Depends(get_db), current_user: User = Depends(require_role(["OPS", "ADMIN"]))):
    case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    payment = db.query(Payment).filter(Payment.id == case.payment_id).first()
    if case.status == "RECOVERED" or (payment and payment.status == "SUCCESS"):
        raise HTTPException(status_code=400, detail="Case already resolved as RECOVERED — cannot perform action")

    operator_label = f"{current_user.name or current_user.email} ({current_user.role})"
    action_type = (payload or {}).get("action_type") or case.customer_action_type or "ADD_FUNDS"
    case.customer_action_status = "COMPLETED"
    case.customer_action_type = action_type
    
    audit_service.record_event(
        db,
        "SIMULATION_TRIGGERED",
        "HUMAN",
        f"Employee ({operator_label}) marked underlying customer payment issue as resolved. Payment remains unrecovered until agent re-evaluation.",
        case_id=case.id
    )
    db.commit()
    db.refresh(case)

    return {
        "case_id": case.id,
        "case_status": case.status,
        "customer_action_status": case.customer_action_status,
        "payment_status": payment.status if payment else "FAILED",
        "message": "Test Mode: Underlying customer payment issue marked as resolved. Payment remains unrecovered until agent re-evaluation."
    }

@router.post("/{case_id}/re-evaluate")
def reevaluate_recovery_case(case_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_role(["OPS", "ADMIN"]))):
    case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    payment = db.query(Payment).filter(Payment.id == case.payment_id).first()
    if case.status == "RECOVERED" or (payment and payment.status == "SUCCESS"):
        raise HTTPException(status_code=400, detail="Case already resolved as RECOVERED — cannot re-evaluate")

    # Backend Timing Enforcement
    now = datetime.now(timezone.utc)
    retry_after = case.retry_after

    if not retry_after:
        raise HTTPException(
            status_code=400,
            detail="No re-evaluation scheduled for this case."
        )

    if retry_after.tzinfo is None:
        retry_after = retry_after.replace(tzinfo=timezone.utc)

    if now < retry_after:
        raise HTTPException(
            status_code=400,
            detail=f"Re-evaluation is not due yet. Next re-evaluation: {retry_after.isoformat()}"
        )

    operator_label = f"{current_user.name or current_user.email} ({current_user.role})"

    audit_service.record_event(
        db,
        "RE-EVALUATION STARTED",
        "HUMAN",
        f"Employee ({operator_label}) manually triggered recovery case re-evaluation.",
        case_id=case.id
    )

    # Idempotency check
    active_run = db.query(AgentRun).filter(AgentRun.case_id == case.id, AgentRun.status.in_(["PENDING", "RUNNING"])).first()
    if active_run:
        return {"run_id": active_run.id, "case_id": case.id, "status": "RE_EVALUATING", "message": "Active run already in progress."}

    new_run = AgentRun(case_id=case.id, status="PENDING", trigger_type="MANUAL_EXECUTE", approved_by=operator_label)
    db.add(new_run)
    db.commit()
    db.refresh(new_run)

    execution_service.run_agent_workflow_sync(new_run.id)
    db.refresh(case)

    return {"run_id": new_run.id, "case_id": case.id, "case_status": case.status, "customer_action_status": case.customer_action_status}

@router.post("/{case_id}/what-if")
def run_what_if_simulation(case_id: str, payload: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Runs a strictly read-only What-If simulation by applying transient parameter overrides
    to case, payment, and customer attributes, running predictions and guardrails in-memory,
    and rolling back the database session.
    """
    db.begin_nested()
    try:
        case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        payment = db.query(Payment).filter(Payment.id == case.payment_id).first()
        customer = db.query(Customer).filter(Customer.id == case.customer_id).first()

        # Capture original baseline metrics
        action = case.recommended_action or "RETRY"
        guardrail_allowed, guardrail_reason, guardrail_checks = policy_engine.validate_action(db, case, action)

        current = {
            "recovery_probability": float(case.recovery_probability or 0.5),
            "recommended_action": action,
            "action_confidence": float(case.agent_confidence or 0.85),
            "guardrail": "ALLOWED" if guardrail_allowed else "BLOCKED",
            "blocking_reason": guardrail_reason if not guardrail_allowed else None
        }

        # Original attributes for comparison text
        orig_amount = float(case.revenue_at_risk or 0.0)
        orig_retry_count = int(case.retry_count or 0)
        orig_opt_out = bool(customer.opted_out if customer else False)
        orig_reason = str(payment.failure_reason if payment else "TRANSIENT_TIMEOUT")
        orig_payment_status = str(payment.status if payment else "FAILED")

        # Apply temporary overrides directly inside the active db session transaction
        overrides = payload.get("overrides", {})
        if "amount" in overrides:
            val = float(overrides["amount"])
            case.revenue_at_risk = val
            if payment:
                payment.amount = val
        if "attempt_number" in overrides:
            val = int(overrides["attempt_number"])
            case.retry_count = val
            if payment:
                payment.attempt_number = val
        if "customer_opted_out" in overrides and customer:
            customer.opted_out = bool(overrides["customer_opted_out"])
        if "failure_reason" in overrides and payment:
            payment.failure_reason = str(overrides["failure_reason"])
            payment.failure_category = str(overrides["failure_reason"])
        if "payment_status" in overrides and payment:
            payment.status = str(overrides["payment_status"])

        # Determine customer tenure and historical billing success
        tenure_months = 12
        if customer and customer.customer_since:
            delta = datetime.now(timezone.utc) - customer.customer_since.replace(tzinfo=timezone.utc)
            tenure_months = max(1, int(delta.days / 30))

        success_rate = 0.85
        if customer:
            success_rate = getattr(customer, 'historical_success_rate', 0.85)
            if success_rate == 0.85 and customer.payments:
                successes = sum(1 for p in customer.payments if p.status == "SUCCESS")
                total = len(customer.payments)
                success_rate = successes / total if total > 0 else 0.85

        # Execute recovery probability model using overrides
        sim_prob = predictor.predict_recovery_probability(
            payment_amount=case.revenue_at_risk,
            failure_category=payment.failure_reason if payment else "TRANSIENT_TIMEOUT",
            customer_ltv=customer.lifetime_value if customer else 500.0,
            customer_tenure=tenure_months,
            attempt_number=case.retry_count,
            previous_failures=case.retry_count - 1 if case.retry_count > 1 else 0,
            historical_success_rate=success_rate,
            payment_method="card"
        )

        # Run diagnosis classification rules using overrides
        sim_cause, sim_cause_conf = predictor.predict_root_cause(
            payment_amount=case.revenue_at_risk,
            failure_reason=payment.failure_reason if payment else "TRANSIENT_TIMEOUT",
            attempt_number=case.retry_count,
            customer_tenure=tenure_months
        )

        # Rerun action-selection predictor using overrides and new predictions
        action_res = action_predictor.predict_action(
            amount_usd=case.revenue_at_risk,
            failure_reason=payment.failure_reason if payment else "TRANSIENT_TIMEOUT",
            attempt_number=case.retry_count,
            customer_opted_out=customer.opted_out if customer else False,
            recovery_probability=sim_prob,
            root_cause=sim_cause,
            root_cause_confidence=sim_cause_conf,
            revenue_at_risk=case.revenue_at_risk,
            expected_recovery=case.revenue_at_risk * sim_prob
        )
        sim_action = action_res["predicted_action"]
        sim_confidence = action_res["confidence"]

        # Run policy guardrails validator
        sim_allowed, sim_reason, sim_checks = policy_engine.validate_action(db, case, sim_action)

        scenario = {
            "recovery_probability": sim_prob,
            "recommended_action": sim_action,
            "action_confidence": sim_confidence,
            "guardrail": "ALLOWED" if sim_allowed else "BLOCKED",
            "blocking_reason": sim_reason if not sim_allowed else None,
            "checks": sim_checks
        }

        # Build comparison logs
        changes = []
        if "amount" in overrides:
            changes.append(f"Amount changed from original: ${orig_amount:,.2f} ➔ ${float(overrides['amount']):,.2f}")
        if "attempt_number" in overrides:
            changes.append(f"Attempt/retry count changed: {orig_retry_count} ➔ {int(overrides['attempt_number'])}")
        if "customer_opted_out" in overrides:
            changes.append(f"Customer Opt-Out status overridden to {overrides['customer_opted_out']}")
        if "failure_reason" in overrides:
            changes.append(f"Decline failure reason changed: '{orig_reason}' ➔ '{overrides['failure_reason']}'")
        if "payment_status" in overrides:
            changes.append(f"Payment status changed: '{orig_payment_status}' ➔ '{overrides['payment_status']}'")

        # Track model and guardrail delta outputs
        if current["recommended_action"] != sim_action:
            changes.append(f"Recommended action changed: {current['recommended_action']} ➔ {sim_action}")
        if abs(current["recovery_probability"] - sim_prob) > 0.01:
            dir_text = "increased" if sim_prob > current["recovery_probability"] else "decreased"
            changes.append(f"Recovery probability {dir_text}: {current['recovery_probability']*100:.0f}% ➔ {sim_prob*100:.0f}%")
        if current["guardrail"] != scenario["guardrail"]:
            changes.append(f"Guardrail status changed: {current['guardrail']} ➔ {scenario['guardrail']}")

        return {
            "current": current,
            "scenario": scenario,
            "changes": changes
        }
    finally:
        db.rollback()

