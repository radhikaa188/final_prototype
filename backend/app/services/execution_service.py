import json
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Generator
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models import (
    RecoveryCase, Payment, Customer, AgentRun, AgentRunStep,
    RecoveryAction, AuditEvent, Policy
)
from app.ml.predictor import predictor
from app.agents.recovery_agent import recovery_agent
from app.policies.guardrails import policy_engine
from app.services.gateway_simulator import gateway_simulator
from app.services.notification_service import notification_service
from app.services.audit_service import audit_service

class ExecutionService:
    @staticmethod
    def run_agent_workflow_sync(run_id: str) -> AgentRun:
        """Synchronous execution of agent run for immediate or background processing"""
        db: Session = SessionLocal()
        try:
            agent_run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
            if not agent_run:
                return None

            case = db.query(RecoveryCase).filter(RecoveryCase.id == agent_run.case_id).first()
            payment = db.query(Payment).filter(Payment.id == case.payment_id).first() if case else None
            customer = db.query(Customer).filter(Customer.id == case.customer_id).first() if case else None

            # Early exit if run or case has already reached a terminal state
            if agent_run.status in ("COMPLETED", "BLOCKED") or (case and case.status in ("RECOVERED", "STOPPED")):
                return agent_run

            agent_run.status = "RUNNING"
            agent_run.started_at = datetime.now(timezone.utc)
            if case and case.status != "RECOVERED":
                case.status = "EXECUTING"
            db.commit()

            steps = [
                ("LOAD_CONTEXT", "Loaded customer profile, payment history, and operational policy rules."),
                ("DIAGNOSE", "Executed ML Model 1 (Root Cause Diagnosis)."),
                ("PREDICT_RECOVERY", "Executed ML Model 2 (Recovery Probability P(Recovery))."),
                ("REVIEW_HISTORY", "Analyzed prior recovery attempts and retry counts."),
                ("SELECT_ACTION", "Recovery Agent evaluated case and selected optimal intervention."),
                ("CHECK_GUARDRAILS", "Policy Engine validated proposed action against operational guardrails."),
                ("EXECUTE", "Invoked execution service & payment gateway connector."),
                ("OBSERVE", "Observed execution outcome from gateway response."),
                ("UPDATE_STATE", "Updated database state for payment, case, and actions."),
                ("NOTIFY", "Dispatched event-driven notifications to customer & operations."),
                ("AUDIT", "Persisted immutable audit trail event record.")
            ]

            step_outputs = {}
            guardrail_passed = True
            action_result = None

            for idx, (step_name, description) in enumerate(steps, start=1):
                # Guard against executing steps for a run/case in terminal state
                if agent_run.status in ("COMPLETED", "BLOCKED") or (case and case.status in ("RECOVERED", "STOPPED")):
                    break

                step = AgentRunStep(
                    run_id=run_id,
                    step_number=idx,
                    step_name=step_name,
                    status="RUNNING",
                    started_at=datetime.now(timezone.utc),
                    input_summary=f"Executing {step_name} for case {case.id}"
                )
                db.add(step)
                db.commit()

                # Execute specific step logic
                if step_name == "LOAD_CONTEXT":
                    out = {"customer": customer.name if customer else "N/A", "amount": payment.amount if payment else 0.0, "current_retries": case.retry_count}
                    step.output_summary = json.dumps(out)
                    step.status = "SUCCESS"

                elif step_name == "DIAGNOSE":
                    cause, conf = predictor.predict_root_cause(
                        payment.amount if payment else 100.0,
                        payment.failure_reason if payment else "DECLINED",
                        payment.failure_category if payment else "TRANSIENT",
                        payment.attempt_number if payment else 1
                    )
                    case.root_cause = cause
                    case.root_cause_confidence = conf
                    step.output_summary = json.dumps({"root_cause": cause, "confidence": conf})
                    step.status = "SUCCESS"
                    audit_service.record_event(db, "CURRENT_CONDITION_CHECKED", "ML", f"Current condition checked: diagnosed root cause {cause} (confidence: {conf*100:.0f}%)", case_id=case.id, agent_run_id=run_id)

                elif step_name == "PREDICT_RECOVERY":
                    prob = predictor.predict_recovery_probability(
                        payment.amount if payment else 100.0,
                        payment.failure_category if payment else "TRANSIENT",
                        customer.lifetime_value if customer else 500.0,
                        12,
                        case.retry_count + 1
                    )
                    case.recovery_probability = prob
                    case.expected_recovery = round(case.revenue_at_risk * prob, 2)
                    case.priority_score = case.expected_recovery
                    step.output_summary = json.dumps({"recovery_probability": prob, "expected_recovery": case.expected_recovery})
                    step.status = "SUCCESS"
                    audit_service.record_event(db, "RECOVERY_PROBABILITY_CALCULATED", "ML", f"Recovery probability calculated: P(Recovery) = {prob*100:.0f}%, Expected Recovery = ${case.expected_recovery:.2f}", case_id=case.id, agent_run_id=run_id)

                elif step_name == "REVIEW_HISTORY":
                    prior_actions = db.query(RecoveryAction).filter(RecoveryAction.case_id == case.id).all()
                    step.output_summary = json.dumps({"prior_actions_count": len(prior_actions), "retry_count": case.retry_count})
                    step.status = "SUCCESS"

                elif step_name == "SELECT_ACTION":
                    is_cust_req, act_type, act_desc = policy_engine.classify_customer_action_requirement(
                        payment.failure_reason if payment else None, case.root_cause
                    )
                    requires_customer = is_cust_req or case.customer_action_required or (case.status == "CUSTOMER_ACTION_REQUIRED" and case.customer_action_status != "COMPLETED")

                    if agent_run.trigger_type in ("MANUAL_APPROVE", "MANUAL_EXECUTE") and agent_run.recommended_action:
                        action = agent_run.recommended_action
                        reason = f"Action '{action}' approved manually by employee (Ops User)."
                        conf = 1.0
                    elif requires_customer and case.customer_action_status != "COMPLETED":
                        action = "CUSTOMER_NUDGE"
                        reason = f"Customer action required ({case.customer_action_type or act_type}). Customer action is currently PENDING. Re-evaluation verified issue remains unresolved; no retry executed."
                        conf = 0.95
                        agent_run.recommended_action = action
                    else:
                        eval_res = recovery_agent.evaluate_case_full(db, case)
                        action = eval_res["recommended_action"]
                        reason = eval_res["reason"]
                        conf = eval_res["confidence"]
                        agent_run.recommended_action = action

                    if case.status != "RECOVERED":
                        case.recommended_action = action
                    case.agent_confidence = conf
                    step.output_summary = json.dumps({
                        "action": action,
                        "reason": reason,
                        "confidence": conf,
                        "ml_used": False if agent_run.trigger_type in ("MANUAL_APPROVE", "MANUAL_EXECUTE") else (not requires_customer or case.customer_action_status == "COMPLETED"),
                        "model": "CustomerActionGuard" if (requires_customer and case.customer_action_status != "COMPLETED") else "HistGradientBoostingClassifier",
                        "probabilities": {action: conf},
                        "risk_assessment": "LOW",
                        "supporting_factors": [
                            f"Customer action state: {case.customer_action_status or 'PENDING'}",
                            f"Root cause: {case.root_cause or 'CUSTOMER_ACTION'}"
                        ]
                    })
                    step.status = "SUCCESS"
                    audit_service.record_event(db, "ACTION_SELECTED", "AGENT", f"Action selected: {action}. Confidence: {conf*100:.0f}%. Reasoning: {reason}", case_id=case.id, agent_run_id=run_id)

                elif step_name == "CHECK_GUARDRAILS":
                    action = agent_run.recommended_action or "CUSTOMER_NUDGE"
                    is_manual = agent_run.trigger_type in ("MANUAL_APPROVE", "MANUAL_EXECUTE")
                    allowed, reason, checks = policy_engine.validate_action(db, case, action, is_manual_approval=is_manual)
                    guardrail_passed = allowed
                    step.output_summary = json.dumps({"allowed": allowed, "reason": reason, "checks": checks})
                    step.status = "SUCCESS" if allowed else "BLOCKED"
                    audit_service.record_event(db, "POLICY_GUARDRAILS_VALIDATED", "POLICY_ENGINE", f"Policy / guardrails validated: proposal to {action} was {'APPROVED' if allowed else 'BLOCKED'} ({reason})", case_id=case.id, agent_run_id=run_id)
                    if not allowed:
                        agent_run.status = "BLOCKED"
                        agent_run.error = reason
                        if case.status != "RECOVERED":
                            if not (case.customer_action_required and case.customer_action_status == "PENDING"):
                                case.status = "STOPPED"
                                case.closed_at = datetime.now(timezone.utc)
                        notification_service.send_notification(
                            db,
                            case.id,
                            customer.id if customer else None,
                            "POLICY_BLOCKED",
                            reason=reason,
                            agent_run_id=run_id
                        )
                        db.commit()
                        break

                elif step_name == "EXECUTE":
                    action = agent_run.recommended_action or "CUSTOMER_NUDGE"
                    is_cust_req, act_type, act_desc = policy_engine.classify_customer_action_requirement(
                        payment.failure_reason if payment else None, case.root_cause
                    )
                    requires_customer = is_cust_req or case.customer_action_required or (case.status == "CUSTOMER_ACTION_REQUIRED" and case.customer_action_status != "COMPLETED")

                    if requires_customer and case.customer_action_status != "COMPLETED":
                        notification_service.send_notification(db, case.id, customer.id if customer else None, "CUSTOMER_NUDGE" if case.customer_notified_at else "CUSTOMER_ACTION_REQUIRED", agent_run_id=run_id)
                        action_result = {
                            "status": "CUSTOMER_ACTION_REQUIRED",
                            "message": f"Customer action ({case.customer_action_type or act_type}) is unresolved (PENDING). Automatic re-evaluation verified issue remains unresolved; no retry executed.",
                            "action_type": case.customer_action_type or act_type
                        }
                    elif requires_customer and case.customer_action_status == "COMPLETED":
                        notification_service.send_notification(db, case.id, customer.id if customer else None, "AUTOMATIC_RETRY_ATTEMPTED", agent_run_id=run_id)
                        action_result = gateway_simulator.process_retry(payment.gateway_payment_id if payment else "pay_test", case.revenue_at_risk, case.retry_count + 1, original_failure_reason=payment.failure_reason if payment else None)
                    elif action == "RETRY":
                        notification_service.send_notification(db, case.id, customer.id if customer else None, "AUTOMATIC_RETRY_ATTEMPTED", agent_run_id=run_id)
                        action_result = gateway_simulator.process_retry(payment.gateway_payment_id if payment else "pay_test", case.revenue_at_risk, case.retry_count + 1, original_failure_reason=payment.failure_reason if payment else None)
                    elif action == "CUSTOMER_NUDGE":
                        notification_service.send_notification(db, case.id, customer.id if customer else None, "CUSTOMER_NUDGE", agent_run_id=run_id)
                        action_result = {
                            "status": "CUSTOMER_ACTION_REQUIRED",
                            "message": "Customer notification dispatched. Awaiting customer action.",
                            "action_type": "CUSTOMER_NUDGE"
                        }
                    elif action == "HUMAN_REVIEW":
                        action_result = {"status": "ESCALATED", "message": "Case routed to Human Operations queue."}
                    else: # STOP
                        action_result = {"status": "STOPPED", "message": "Automated recovery halted by policy/agent."}

                    step.output_summary = json.dumps(action_result)
                    step.status = "SUCCESS"
                    audit_service.record_event(db, "RECOVERY_ACTION_EXECUTED", "EXECUTOR", f"Recovery action evaluated/executed: {action}", case_id=case.id, agent_run_id=run_id)

                elif step_name == "OBSERVE":
                    status_str = action_result.get("status") if action_result else "UNKNOWN"
                    step.output_summary = json.dumps({"observed_status": status_str, "details": action_result})
                    step.status = "SUCCESS"
                    audit_service.record_event(db, "PAYMENT_RESULT_RECEIVED", "GATEWAY", f"Payment result received from gateway: status is {status_str}. Details: {action_result.get('message') if action_result else ''}", case_id=case.id, agent_run_id=run_id)

                elif step_name == "UPDATE_STATE":
                    action_type = agent_run.recommended_action or "RETRY"
                    exec_status = action_result.get("status") if action_result else "FAILED"
                    
                    # Create recovery action record
                    rec_action = RecoveryAction(
                        case_id=case.id,
                        agent_run_id=run_id,
                        action_type=action_type,
                        status=exec_status,
                        reason=action_result.get("message") if action_result else "",
                        result=json.dumps(action_result) if action_result else "",
                        amount_recovered=action_result.get("amount_recovered", 0.0) if action_result else 0.0
                    )
                    db.add(rec_action)

                    if exec_status == "SUCCESS":
                        payment.status = "SUCCESS"
                        case.status = "RECOVERED"
                        case.closed_at = datetime.now(timezone.utc)
                        case.recommended_action = action_type
                        case.next_action = "NONE"
                        case.customer_action_status = "CANCELLED"
                        agent_run.final_result = "RECOVERED"
                        audit_service.record_event(
                            db,
                            "RECOVERED",
                            "SYSTEM",
                            f"Payment recovered successfully. Recovery case status marked RECOVERED.",
                            case_id=case.id,
                            agent_run_id=run_id
                        )
                    elif exec_status == "CUSTOMER_ACTION_REQUIRED":
                        policy = policy_engine.get_active_policy(db)
                        now = datetime.now(timezone.utc)
                        case.status = "CUSTOMER_ACTION_REQUIRED"
                        case.customer_action_required = True
                        case.customer_action_type = case.customer_action_type or action_result.get("action_type", "OTHER")
                        case.customer_action_description = case.customer_action_description or action_result.get("message", "Customer action required.")
                        if not case.waiting_since:
                            case.waiting_since = now
                        case.retry_after = now + timedelta(hours=policy.customer_action_wait_hours)
                        if not case.expires_at:
                            case.expires_at = now + timedelta(hours=policy.customer_action_expire_hours)
                        case.customer_action_status = "PENDING"
                        case.next_action = "WAIT_FOR_CUSTOMER_ACTION"
                        agent_run.final_result = "CUSTOMER_ACTION_REQUIRED"
                        audit_service.record_event(
                            db,
                            "CUSTOMER_ACTION_PENDING",
                            "SYSTEM",
                            f"Re-evaluation confirmed customer action ({case.customer_action_type}) is unresolved: status remains PENDING. No retry executed.",
                            case_id=case.id,
                            agent_run_id=run_id
                        )
                    elif exec_status == "ESCALATED":
                        case.status = "ESCALATED"
                        case.next_action = "HUMAN_REVIEW"
                        agent_run.final_result = "ESCALATED"
                    elif exec_status == "STOPPED":
                        case.status = "STOPPED"
                        case.next_action = "NONE"
                        agent_run.final_result = "STOPPED"
                    else: # FAILED
                        case.retry_count += 1
                        now = datetime.now(timezone.utc)
                        if case.retry_count >= 3:
                            case.status = "STOPPED"
                            case.next_action = "NONE"
                            case.closed_at = now
                            agent_run.final_result = "STOPPED_MAX_RETRIES"
                            audit_service.record_event(
                                db,
                                "RECOVERY_STOPPED",
                                "SYSTEM",
                                f"Maximum recovery attempts ({case.retry_count}/3) reached. Automated recovery stopped.",
                                case_id=case.id,
                                agent_run_id=run_id
                            )
                        else:
                            case.status = "RE_EVALUATING"
                            case.next_action = "RE_EVALUATE"
                            agent_run.final_result = "RETRY_FAILED"
                            policy = policy_engine.get_active_policy(db)
                            backoff_hours = getattr(policy, "retry_backoff_hours", 1)
                            case.waiting_since = now
                            case.retry_after = now + timedelta(hours=backoff_hours)
                            audit_service.record_event(
                                db,
                                "RECOVERY_ATTEMPT_FAILED",
                                "SYSTEM",
                                f"Recovery attempt #{case.retry_count} failed. Case marked RE_EVALUATING. Next re-evaluation scheduled for {case.retry_after.isoformat()}.",
                                case_id=case.id,
                                agent_run_id=run_id
                            )

                    step.output_summary = json.dumps({"new_case_status": case.status, "payment_status": payment.status})
                    step.status = "SUCCESS"


                elif step_name == "NOTIFY":
                    if case.status == "RECOVERED":
                        event_type = "RECOVERY_SUCCESS"
                    elif case.status == "CUSTOMER_ACTION_REQUIRED":
                        event_type = "CUSTOMER_ACTION_REQUIRED"
                    elif case.status == "ESCALATED":
                        event_type = "HUMAN_REVIEW_REQUIRED"
                    elif case.status == "STOPPED":
                        event_type = "RECOVERY_STOPPED"
                    else:
                        event_type = "RETRY_FAILED"

                    notification_service.send_notification(db, case.id, customer.id if customer else None, event_type, agent_run_id=run_id)
                    step.output_summary = json.dumps({"notification_sent": event_type})
                    step.status = "SUCCESS"

                elif step_name == "AUDIT":
                    audit_service.record_event(db, "WORKFLOW_COMPLETED", "SYSTEM", f"Agent run completed with final case status: {case.status}", case_id=case.id, agent_run_id=run_id)
                    step.output_summary = json.dumps({"audit_logged": True})
                    step.status = "SUCCESS"

                step.completed_at = datetime.now(timezone.utc)
                db.commit()

            if agent_run.status != "BLOCKED":
                agent_run.status = "COMPLETED"
            agent_run.completed_at = datetime.now(timezone.utc)
            db.commit()

            db.refresh(agent_run)
            db.expunge(agent_run)
            return agent_run

        finally:
            db.close()

    @staticmethod
    def stream_agent_steps(run_id: str) -> Generator[str, None, None]:
        """SSE Generator that executes steps with short real-time timing delays and streams JSON events"""
        db: Session = SessionLocal()
        try:
            agent_run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
            if not agent_run:
                yield f"data: {json.dumps({'error': 'Agent run not found'})}\n\n"
                return

            case = db.query(RecoveryCase).filter(RecoveryCase.id == agent_run.case_id).first()
            payment = db.query(Payment).filter(Payment.id == case.payment_id).first() if case else None
            customer = db.query(Customer).filter(Customer.id == case.customer_id).first() if case else None

            # Early exit if run or case has already reached a terminal state
            if agent_run.status in ("COMPLETED", "BLOCKED") or (case and case.status in ("RECOVERED", "STOPPED")):
                yield {"data": json.dumps({'run_id': run_id, 'event': 'COMPLETE', 'final_result': agent_run.final_result or agent_run.status, 'case_status': case.status if case else 'COMPLETED'})}
                return

            agent_run.status = "RUNNING"
            agent_run.started_at = datetime.now(timezone.utc)
            if case and case.status != "RECOVERED":
                case.status = "EXECUTING"
            db.commit()

            steps = [
                ("LOAD_CONTEXT", "Loaded customer profile, payment history, and operational policy rules."),
                ("DIAGNOSE", "Executed ML Model 1 (Root Cause Diagnosis)."),
                ("PREDICT_RECOVERY", "Executed ML Model 2 (Recovery Probability P(Recovery))."),
                ("REVIEW_HISTORY", "Analyzed prior recovery attempts and retry counts."),
                ("SELECT_ACTION", "Recovery Agent evaluated case and selected optimal intervention."),
                ("CHECK_GUARDRAILS", "Policy Engine validated proposed action against operational guardrails."),
                ("EXECUTE", "Invoked execution service & payment gateway connector."),
                ("OBSERVE", "Observed execution outcome from gateway response."),
                ("UPDATE_STATE", "Updated database state for payment, case, and actions."),
                ("NOTIFY", "Dispatched event-driven notifications to customer & operations."),
                ("AUDIT", "Persisted immutable audit trail event record.")
            ]

            action_result = None

            for idx, (step_name, description) in enumerate(steps, start=1):
                # Guard against executing steps for a run/case in terminal state
                if agent_run.status in ("COMPLETED", "BLOCKED") or (case and case.status in ("RECOVERED", "STOPPED")):
                    break

                # Emit step start
                step = AgentRunStep(
                    run_id=run_id,
                    step_number=idx,
                    step_name=step_name,
                    status="RUNNING",
                    started_at=datetime.now(timezone.utc),
                    input_summary=description
                )
                db.add(step)
                db.commit()

                event_data = {
                    "run_id": run_id,
                    "step_number": idx,
                    "step_name": step_name,
                    "status": "RUNNING",
                    "description": description,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                yield {"data": json.dumps(event_data)}
                time.sleep(0.3) # Real-time visual delay

                # Step computations
                output_data = {}
                if step_name == "LOAD_CONTEXT":
                    output_data = {"customer": customer.name if customer else "N/A", "amount": payment.amount if payment else 0.0, "current_retries": case.retry_count}

                elif step_name == "DIAGNOSE":
                    cause, conf = predictor.predict_root_cause(
                        payment.amount if payment else 100.0,
                        payment.failure_reason if payment else "DECLINED",
                        payment.failure_category if payment else "TRANSIENT",
                        payment.attempt_number if payment else 1
                    )
                    case.root_cause = cause
                    case.root_cause_confidence = conf
                    output_data = {"root_cause": cause, "confidence": conf}
                    audit_service.record_event(db, "CURRENT_CONDITION_CHECKED", "ML", f"Current condition checked: diagnosed root cause {cause} (confidence: {conf*100:.0f}%)", case_id=case.id, agent_run_id=run_id)

                elif step_name == "PREDICT_RECOVERY":
                    prob = predictor.predict_recovery_probability(
                        payment.amount if payment else 100.0,
                        payment.failure_category if payment else "TRANSIENT",
                        customer.lifetime_value if customer else 500.0,
                        12,
                        case.retry_count + 1
                    )
                    case.recovery_probability = prob
                    case.expected_recovery = round(case.revenue_at_risk * prob, 2)
                    case.priority_score = case.expected_recovery
                    output_data = {"recovery_probability": prob, "expected_recovery": case.expected_recovery}
                    audit_service.record_event(db, "RECOVERY_PROBABILITY_CALCULATED", "ML", f"Recovery probability calculated: P(Recovery) = {prob*100:.0f}%, Expected Recovery = ${case.expected_recovery:.2f}", case_id=case.id, agent_run_id=run_id)

                elif step_name == "REVIEW_HISTORY":
                    prior_actions = db.query(RecoveryAction).filter(RecoveryAction.case_id == case.id).all()
                    output_data = {"prior_actions_count": len(prior_actions), "retry_count": case.retry_count}

                elif step_name == "SELECT_ACTION":
                    is_cust_req, act_type, act_desc = policy_engine.classify_customer_action_requirement(
                        payment.failure_reason if payment else None, case.root_cause
                    )
                    requires_customer = is_cust_req or case.customer_action_required or (case.status == "CUSTOMER_ACTION_REQUIRED" and case.customer_action_status != "COMPLETED")

                    if agent_run.trigger_type in ("MANUAL_APPROVE", "MANUAL_EXECUTE") and agent_run.recommended_action:
                        action = agent_run.recommended_action
                        reason = f"Action '{action}' approved manually by employee (Ops User)."
                        conf = 1.0
                    elif requires_customer and case.customer_action_status != "COMPLETED":
                        action = "CUSTOMER_NUDGE"
                        reason = f"Customer action required ({case.customer_action_type or act_type}). Customer action is currently PENDING. Re-evaluation verified issue remains unresolved; no retry executed."
                        conf = 0.95
                        agent_run.recommended_action = action
                    else:
                        eval_res = recovery_agent.evaluate_case_full(db, case)
                        action = eval_res["recommended_action"]
                        reason = eval_res["reason"]
                        conf = eval_res["confidence"]
                        agent_run.recommended_action = action

                    if case.status != "RECOVERED":
                        case.recommended_action = action
                    case.agent_confidence = conf
                    output_data = {
                        "action": action,
                        "reason": reason,
                        "confidence": conf,
                        "ml_used": False if agent_run.trigger_type in ("MANUAL_APPROVE", "MANUAL_EXECUTE") else (not requires_customer or case.customer_action_status == "COMPLETED"),
                        "model": "CustomerActionGuard" if (requires_customer and case.customer_action_status != "COMPLETED") else "HistGradientBoostingClassifier",
                        "probabilities": {action: conf},
                        "risk_assessment": "LOW",
                        "supporting_factors": [
                            f"Customer action state: {case.customer_action_status or 'PENDING'}",
                            f"Root cause: {case.root_cause or 'CUSTOMER_ACTION'}"
                        ]
                    }
                    audit_service.record_event(db, "ACTION_SELECTED", "AGENT", f"Action selected: {action}. Confidence: {conf*100:.0f}%. Reasoning: {reason}", case_id=case.id, agent_run_id=run_id)

                elif step_name == "CHECK_GUARDRAILS":
                    action = agent_run.recommended_action or "CUSTOMER_NUDGE"
                    is_manual = agent_run.trigger_type in ("MANUAL_APPROVE", "MANUAL_EXECUTE")
                    allowed, reason, checks = policy_engine.validate_action(db, case, action, is_manual_approval=is_manual)
                    output_data = {"allowed": allowed, "reason": reason, "checks": checks}
                    audit_service.record_event(db, "POLICY_GUARDRAILS_VALIDATED", "POLICY_ENGINE", f"Policy / guardrails validated: proposal to {action} was {'APPROVED' if allowed else 'BLOCKED'} ({reason})", case_id=case.id, agent_run_id=run_id)
                    if not allowed:
                        step.status = "BLOCKED"
                        step.output_summary = json.dumps(output_data)
                        step.completed_at = datetime.now(timezone.utc)
                        agent_run.status = "BLOCKED"
                        agent_run.error = reason
                        if case.status != "RECOVERED":
                            if not (case.customer_action_required and case.customer_action_status == "PENDING"):
                                case.status = "STOPPED"
                                case.closed_at = datetime.now(timezone.utc)
                        notification_service.send_notification(
                            db,
                            case.id,
                            customer.id if customer else None,
                            "POLICY_BLOCKED",
                            reason=reason,
                            agent_run_id=run_id
                        )
                        db.commit()
                        yield {"data": json.dumps({'run_id': run_id, 'step_name': step_name, 'status': 'BLOCKED', 'output': output_data, 'timestamp': datetime.now(timezone.utc).isoformat()})}
                        break

                elif step_name == "EXECUTE":
                    action = agent_run.recommended_action or "CUSTOMER_NUDGE"
                    is_cust_req, act_type, act_desc = policy_engine.classify_customer_action_requirement(
                        payment.failure_reason if payment else None, case.root_cause
                    )
                    requires_customer = is_cust_req or case.customer_action_required or (case.status == "CUSTOMER_ACTION_REQUIRED" and case.customer_action_status != "COMPLETED")

                    if requires_customer and case.customer_action_status != "COMPLETED":
                        notification_service.send_notification(db, case.id, customer.id if customer else None, "CUSTOMER_NUDGE" if case.customer_notified_at else "CUSTOMER_ACTION_REQUIRED", agent_run_id=run_id)
                        action_result = {
                            "status": "CUSTOMER_ACTION_REQUIRED",
                            "message": f"Customer action ({case.customer_action_type or act_type}) is unresolved (PENDING). Automatic re-evaluation verified issue remains unresolved; no retry executed.",
                            "action_type": case.customer_action_type or act_type
                        }
                    elif requires_customer and case.customer_action_status == "COMPLETED":
                        notification_service.send_notification(db, case.id, customer.id if customer else None, "AUTOMATIC_RETRY_ATTEMPTED", agent_run_id=run_id)
                        action_result = gateway_simulator.process_retry(payment.gateway_payment_id if payment else "pay_test", case.revenue_at_risk, case.retry_count + 1, original_failure_reason=payment.failure_reason if payment else None)
                    elif action == "RETRY":
                        notification_service.send_notification(db, case.id, customer.id if customer else None, "AUTOMATIC_RETRY_ATTEMPTED", agent_run_id=run_id)
                        action_result = gateway_simulator.process_retry(payment.gateway_payment_id if payment else "pay_test", case.revenue_at_risk, case.retry_count + 1, original_failure_reason=payment.failure_reason if payment else None)
                    elif action == "CUSTOMER_NUDGE":
                        notification_service.send_notification(db, case.id, customer.id if customer else None, "CUSTOMER_NUDGE", agent_run_id=run_id)
                        action_result = {
                            "status": "CUSTOMER_ACTION_REQUIRED",
                            "message": "Customer notification dispatched. Awaiting customer action.",
                            "action_type": "CUSTOMER_NUDGE"
                        }
                    elif action == "HUMAN_REVIEW":
                        action_result = {"status": "ESCALATED", "message": "Case routed to Human Operations queue."}
                    else: # STOP
                        action_result = {"status": "STOPPED", "message": "Automated recovery halted by policy/agent."}
                    output_data = action_result
                    audit_service.record_event(db, "RECOVERY_ACTION_EXECUTED", "EXECUTOR", f"Recovery action evaluated/executed: {action}", case_id=case.id, agent_run_id=run_id)

                elif step_name == "OBSERVE":
                    status_str = action_result.get("status") if action_result else "UNKNOWN"
                    output_data = {"observed_status": status_str, "details": action_result}
                    audit_service.record_event(db, "PAYMENT_RESULT_RECEIVED", "GATEWAY", f"Payment result received from gateway: status is {status_str}. Details: {action_result.get('message') if action_result else ''}", case_id=case.id, agent_run_id=run_id)

                elif step_name == "UPDATE_STATE":
                    action_type = agent_run.recommended_action or "RETRY"
                    exec_status = action_result.get("status") if action_result else "FAILED"
                    
                    rec_action = RecoveryAction(
                        case_id=case.id,
                        agent_run_id=run_id,
                        action_type=action_type,
                        status=exec_status,
                        reason=action_result.get("message") if action_result else "",
                        result=json.dumps(action_result) if action_result else "",
                        amount_recovered=action_result.get("amount_recovered", 0.0) if action_result else 0.0
                    )
                    db.add(rec_action)

                    if exec_status == "SUCCESS":
                        payment.status = "SUCCESS"
                        case.status = "RECOVERED"
                        case.closed_at = datetime.now(timezone.utc)
                        case.recommended_action = action_type
                        case.next_action = "NONE"
                        case.customer_action_status = "CANCELLED"
                        agent_run.final_result = "RECOVERED"
                        audit_service.record_event(
                            db,
                            "RECOVERED",
                            "SYSTEM",
                            f"Payment recovered successfully. Recovery case status marked RECOVERED.",
                            case_id=case.id,
                            agent_run_id=run_id
                        )
                    elif exec_status == "CUSTOMER_ACTION_REQUIRED":
                        policy = policy_engine.get_active_policy(db)
                        now = datetime.now(timezone.utc)
                        case.status = "CUSTOMER_ACTION_REQUIRED"
                        case.customer_action_required = True
                        case.customer_action_type = case.customer_action_type or action_result.get("action_type", "OTHER")
                        case.customer_action_description = case.customer_action_description or action_result.get("message", "Customer action required.")
                        if not case.waiting_since:
                            case.waiting_since = now
                        case.retry_after = now + timedelta(hours=policy.customer_action_wait_hours)
                        if not case.expires_at:
                            case.expires_at = now + timedelta(hours=policy.customer_action_expire_hours)
                        case.customer_action_status = "PENDING"
                        case.next_action = "WAIT_FOR_CUSTOMER_ACTION"
                        agent_run.final_result = "CUSTOMER_ACTION_REQUIRED"
                        audit_service.record_event(
                            db,
                            "CUSTOMER_ACTION_PENDING",
                            "SYSTEM",
                            f"Re-evaluation confirmed customer action ({case.customer_action_type}) is unresolved: status remains PENDING. No retry executed.",
                            case_id=case.id,
                            agent_run_id=run_id
                        )
                    elif exec_status == "ESCALATED":
                        case.status = "ESCALATED"
                        case.next_action = "HUMAN_REVIEW"
                        agent_run.final_result = "ESCALATED"
                    elif exec_status == "STOPPED":
                        case.status = "STOPPED"
                        case.next_action = "NONE"
                        agent_run.final_result = "STOPPED"
                    else: # FAILED
                        case.retry_count += 1
                        now = datetime.now(timezone.utc)
                        if case.retry_count >= 3:
                            case.status = "STOPPED"
                            case.next_action = "NONE"
                            case.closed_at = now
                            agent_run.final_result = "STOPPED_MAX_RETRIES"
                            audit_service.record_event(
                                db,
                                "RECOVERY_STOPPED",
                                "SYSTEM",
                                f"Maximum recovery attempts ({case.retry_count}/3) reached. Automated recovery stopped.",
                                case_id=case.id,
                                agent_run_id=run_id
                            )
                        else:
                            case.status = "RE_EVALUATING"
                            case.next_action = "RE_EVALUATE"
                            agent_run.final_result = "RETRY_FAILED"
                            policy = policy_engine.get_active_policy(db)
                            backoff_hours = getattr(policy, "retry_backoff_hours", 1)
                            case.waiting_since = now
                            case.retry_after = now + timedelta(hours=backoff_hours)
                            audit_service.record_event(
                                db,
                                "RECOVERY_ATTEMPT_FAILED",
                                "SYSTEM",
                                f"Recovery attempt #{case.retry_count} failed. Case marked RE_EVALUATING. Next re-evaluation scheduled for {case.retry_after.isoformat()}.",
                                case_id=case.id,
                                agent_run_id=run_id
                            )

                    output_data = {"new_case_status": case.status, "payment_status": payment.status, "recovered_amount": action_result.get("amount_recovered", 0.0) if action_result else 0.0}


                elif step_name == "NOTIFY":
                    if case.status == "RECOVERED":
                        event_type = "RECOVERY_SUCCESS"
                    elif case.status == "CUSTOMER_ACTION_REQUIRED":
                        event_type = "CUSTOMER_ACTION_REQUIRED"
                    elif case.status == "ESCALATED":
                        event_type = "HUMAN_REVIEW_REQUIRED"
                    elif case.status == "STOPPED":
                        event_type = "RECOVERY_STOPPED"
                    else:
                        event_type = "RETRY_FAILED"

                    notification_service.send_notification(db, case.id, customer.id if customer else None, event_type, agent_run_id=run_id)
                    output_data = {"notification_sent": event_type}

                elif step_name == "AUDIT":
                    audit_service.record_event(db, "WORKFLOW_COMPLETED", "SYSTEM", f"Agent run completed with final case status: {case.status}", case_id=case.id, agent_run_id=run_id)
                    output_data = {"audit_logged": True}

                step.status = "SUCCESS"
                step.output_summary = json.dumps(output_data)
                step.completed_at = datetime.now(timezone.utc)
                db.commit()

                yield {"data": json.dumps({'run_id': run_id, 'step_name': step_name, 'status': 'SUCCESS', 'output': output_data, 'timestamp': datetime.now(timezone.utc).isoformat()})}

            if agent_run.status != "BLOCKED":
                agent_run.status = "COMPLETED"
            agent_run.completed_at = datetime.now(timezone.utc)
            db.commit()

            yield {"data": json.dumps({'run_id': run_id, 'event': 'COMPLETE', 'final_result': agent_run.final_result, 'case_status': case.status})}

        finally:
            db.close()

execution_service = ExecutionService()
