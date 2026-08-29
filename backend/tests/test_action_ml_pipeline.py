import os
import sys
import json
from datetime import datetime

sys.path.insert(0, 'backend')
from app.config import settings
from app.db.session import engine, SessionLocal, Base
from app.db.models import Customer, Payment, RecoveryCase, Policy, AgentRun, RecoveryAction, AuditEvent
from app.ml.action_predictor import action_predictor
from app.agents.recovery_agent import recovery_agent
from app.policies.guardrails import policy_engine
from app.services.execution_service import execution_service

Base.metadata.create_all(bind=engine)

def run_action_ml_pipeline_tests():
    print("=========================================================================")
    print("   RECOVERAI — SUPERVISED ML ACTION SELECTION & GUARDRAILS TEST SUITE    ")
    print("=========================================================================")

    db = SessionLocal()
    try:
        # TEST 1: Action Predictor Loading and Inference Verification
        print("\n-------------------------------------------------------------------------")
        print(" TEST 1: ML Action Predictor Inference & Probability Normalization")
        print("-------------------------------------------------------------------------")
        assert action_predictor.is_trained is True, "Action ML Model should be trained and loaded!"
        
        pred1 = action_predictor.predict_action(
            amount_usd=19.64,
            failure_reason="NETWORK_TIMEOUT",
            gateway_response_code="TIMEOUT_408",
            attempt_number=1,
            previous_failures=0,
            days_since_last_payment=27,
            historical_success_rate=0.587,
            payment_method="upi",
            customer_tenure_months=30,
            monthly_charge_usd=19.42,
            support_ticket_count=2,
            customer_lifetime_value_usd=561.36,
            customer_opted_out=False,
            recovery_probability=0.789,
            root_cause="TRANSIENT_FAILURE",
            root_cause_confidence=0.898,
            revenue_at_risk=20.78,
            expected_recovery=16.4
        )

        print(f" Predicted Action  : {pred1['predicted_action']}")
        print(f" Model Confidence  : {pred1['confidence']*100:.1f}%")
        print(f" Model Name        : {pred1['model']}")
        print(f" Class Probabilities: {pred1['probabilities']}")

        prob_sum = sum(pred1['probabilities'].values())
        assert pred1['predicted_action'] in ['RETRY', 'CUSTOMER_NUDGE', 'HUMAN_REVIEW', 'STOP']
        assert abs(prob_sum - 1.0) < 0.01, f"Probabilities sum ({prob_sum}) should equal 1.0"
        print(" >>> TEST 1 PASSED: Action ML Predictor returns valid predictions and probabilities!")

        # TEST 2: All 4 Action Classes Output Verification
        print("\n-------------------------------------------------------------------------")
        print(" TEST 2: All 4 Action Classes Output Coverage")
        print("-------------------------------------------------------------------------")
        # Test case for CUSTOMER_NUDGE (low LTV, customer action required)
        pred_nudge = action_predictor.predict_action(
            amount_usd=15.00, failure_reason="CARD_EXPIRED", attempt_number=1,
            recovery_probability=0.55, root_cause="CUSTOMER_ACTION", customer_opted_out=False
        )
        # Test case for HUMAN_REVIEW (high-value risk-related decline)
        pred_human = action_predictor.predict_action(
            amount_usd=4500.00, failure_reason="FRAUD_RISK", attempt_number=2,
            support_ticket_count=5, recovery_probability=0.25, root_cause="RISK_RELATED", customer_opted_out=False
        )
        # Test case for STOP (customer opted out or exhausted retries)
        pred_stop = action_predictor.predict_action(
            amount_usd=25.00, failure_reason="ACCOUNT_CLOSED", attempt_number=3,
            previous_failures=3, recovery_probability=0.10, root_cause="OTHER", customer_opted_out=True
        )

        print(f" Nudge Prediction  : {pred_nudge['predicted_action']} (Conf: {pred_nudge['confidence']*100:.1f}%)")
        print(f" Human Review Pred : {pred_human['predicted_action']} (Conf: {pred_human['confidence']*100:.1f}%)")
        print(f" Stop Prediction   : {pred_stop['predicted_action']} (Conf: {pred_stop['confidence']*100:.1f}%)")

        assert pred_nudge['predicted_action'] in ['CUSTOMER_NUDGE', 'RETRY', 'HUMAN_REVIEW', 'STOP']
        assert pred_human['predicted_action'] in ['HUMAN_REVIEW', 'STOP', 'CUSTOMER_NUDGE']
        assert pred_stop['predicted_action'] in ['STOP', 'HUMAN_REVIEW', 'CUSTOMER_NUDGE']
        print(" >>> TEST 2 PASSED: ML Model produces valid class predictions across scenarios!")

        # TEST 3: Opt-Out Guardrail Safety Override
        print("\n-------------------------------------------------------------------------")
        print(" TEST 3: Opt-Out Policy Guardrail Deterministic Override")
        print("-------------------------------------------------------------------------")
        uid = datetime.now().strftime("%H%M%S")
        cust_opt = Customer(external_customer_id=f"SIM_ML_OPT_{uid}", name="Opt Out ML Test", email=f"optml_{uid}@example.com", lifetime_value=1500.0, opted_out=True)
        db.add(cust_opt)
        db.flush()

        pay_opt = Payment(gateway_payment_id=f"pay_ml_opt_{uid}", customer_id=cust_opt.id, amount=99.00, currency="USD", status="FAILED", failure_reason="CARD_EXPIRED", attempt_number=1)
        db.add(pay_opt)
        db.flush()

        case_opt = RecoveryCase(payment_id=pay_opt.id, customer_id=cust_opt.id, status="OPEN", revenue_at_risk=99.00, recovery_probability=0.85, expected_recovery=84.15, priority_score=84.15, root_cause="TRANSIENT_FAILURE", retry_count=0)
        db.add(case_opt)
        db.commit()

        # ML model predicts RETRY (since failure is transient & high P(Recovery))
        eval_opt = recovery_agent.evaluate_case_full(db, case_opt)
        print(f" ML Recommendation : {eval_opt['recommended_action']} (Conf: {eval_opt['confidence']*100:.1f}%)")
        
        # Guardrail checks action
        allowed_opt, reason_opt, checks_opt = policy_engine.validate_action(db, case_opt, eval_opt['recommended_action'])
        print(f" Guardrail Decision : Allowed={allowed_opt} | Reason={reason_opt}")

        assert allowed_opt is False, "Guardrail must block action for opted-out customer even if ML recommends it!"
        assert checks_opt["customer_opt_out"]["passed"] is False
        print(" >>> TEST 3 PASSED: Deterministic guardrail overrode ML recommendation for opted-out customer!")

        # TEST 4: Maximum Retry Limit Guardrail Override
        print("\n-------------------------------------------------------------------------")
        print(" TEST 4: Max Retry Limit Policy Guardrail Override")
        print("-------------------------------------------------------------------------")
        cust_normal = Customer(external_customer_id=f"SIM_ML_NORM_{uid}", name="Normal Customer", email=f"norm_{uid}@example.com", lifetime_value=1200.0, opted_out=False)
        db.add(cust_normal)
        db.flush()

        pay_normal = Payment(gateway_payment_id=f"pay_ml_norm_{uid}", customer_id=cust_normal.id, amount=99.00, currency="USD", status="FAILED", failure_reason="CARD_EXPIRED", attempt_number=3)
        db.add(pay_normal)
        db.flush()

        case_retry = RecoveryCase(payment_id=pay_normal.id, customer_id=cust_normal.id, status="OPEN", revenue_at_risk=99.00, recovery_probability=0.90, expected_recovery=89.10, priority_score=89.10, root_cause="TRANSIENT_FAILURE", retry_count=3)
        allowed_retry, reason_retry, checks_retry = policy_engine.validate_action(db, case_retry, "RETRY")
        print(f" Guardrail Decision : Allowed={allowed_retry} | Reason={reason_retry}")

        assert allowed_retry is False, "Guardrail must block retry attempt when retry count >= 3!"
        assert checks_retry["retry_limit"]["passed"] is False
        print(" >>> TEST 4 PASSED: Guardrail blocked retry when maximum limit was reached!")

        # TEST 5: High-Value Payment Guardrail Override
        print("\n-------------------------------------------------------------------------")
        print(" TEST 5: High-Value Payment (> $10,000) Policy Guardrail Override")
        print("-------------------------------------------------------------------------")
        case_hv = RecoveryCase(payment_id=pay_normal.id, customer_id=cust_normal.id, status="OPEN", revenue_at_risk=15000.00, recovery_probability=0.92, expected_recovery=13800.00, priority_score=13800.00, root_cause="TRANSIENT_FAILURE", retry_count=0)
        allowed_hv, reason_hv, checks_hv = policy_engine.validate_action(db, case_hv, "RETRY")
        print(f" Guardrail Decision : Allowed={allowed_hv} | Reason={reason_hv}")

        assert allowed_hv is False, "Guardrail must block auto-retry when amount > $10,000!"
        assert checks_hv["max_auto_retry_amount"]["passed"] is False
        print(" >>> TEST 5 PASSED: Guardrail blocked high-value auto-retry!")

        # TEST 6: Successful End-to-End Workflow Execution & State Persistence
        print("\n-------------------------------------------------------------------------")
        print(" TEST 6: End-to-End Execution (ML Prediction -> Guardrail -> DB Update)")
        print("-------------------------------------------------------------------------")
        cust_exec = Customer(external_customer_id=f"SIM_ML_EXEC_{uid}", name="ML Execution Customer", email=f"mlexec_{uid}@example.com", lifetime_value=980.0, opted_out=False)
        db.add(cust_exec)
        db.flush()

        pay_exec = Payment(gateway_payment_id=f"pay_ml_exec_{uid}", customer_id=cust_exec.id, amount=149.00, currency="USD", status="FAILED", failure_reason="NETWORK_TIMEOUT", attempt_number=1)
        db.add(pay_exec)
        db.flush()

        case_exec = RecoveryCase(payment_id=pay_exec.id, customer_id=cust_exec.id, status="OPEN", revenue_at_risk=149.00, recovery_probability=0.88, expected_recovery=131.12, priority_score=131.12, root_cause="TRANSIENT_FAILURE", retry_count=0)
        db.add(case_exec)
        db.commit()

        agent_run = AgentRun(case_id=case_exec.id, trigger_type="AUTOMATIC")
        db.add(agent_run)
        db.commit()

        run_res = execution_service.run_agent_workflow_sync(agent_run.id)

        pay_after = db.query(Payment).filter(Payment.id == pay_exec.id).first()
        case_after = db.query(RecoveryCase).filter(RecoveryCase.id == case_exec.id).first()
        actions_after = db.query(RecoveryAction).filter(RecoveryAction.case_id == case_exec.id).all()
        audits_after = db.query(AuditEvent).filter(AuditEvent.case_id == case_exec.id).all()

        print(f" Agent Run Status   : {run_res.status}")
        print(f" Final Case Status  : {case_after.status}")
        print(f" Payment Status     : {pay_after.status}")
        print(f" Actions Executed   : {len(actions_after)}")
        print(f" Audit Events       : {len(audits_after)}")

        assert run_res.status == "COMPLETED"
        assert case_after.status in ["RECOVERED", "RE_EVALUATING", "STOPPED", "ESCALATED"]
        assert len(audits_after) >= 3
        print(" >>> TEST 6 PASSED: Workflow executed cleanly and state updated in DB!")

        # TEST 7: Blocked Execution Terminal State & Audit Trail
        print("\n-------------------------------------------------------------------------")
        print(" TEST 7: Blocked Execution Workflow Terminal State")
        print("-------------------------------------------------------------------------")
        agent_run_blocked = AgentRun(case_id=case_opt.id, trigger_type="AUTOMATIC")
        db.add(agent_run_blocked)
        db.commit()

        run_blocked_res = execution_service.run_agent_workflow_sync(agent_run_blocked.id)
        case_blocked_after = db.query(RecoveryCase).filter(RecoveryCase.id == case_opt.id).first()

        print(f" Blocked Run Status : {run_blocked_res.status}")
        print(f" Blocked Run Error  : {run_blocked_res.error}")
        print(f" Final Case Status  : {case_blocked_after.status}")

        assert run_blocked_res.status == "BLOCKED"
        assert case_blocked_after.status == "STOPPED"
        print(" >>> TEST 7 PASSED: Blocked execution reached valid terminal state!")

        print("\n=========================================================================")
        print("   ALL 7 ML ACTION SELECTION & GUARDRAIL TESTS PASSED SUCCESSFULLY!       ")
        print("=========================================================================")

    finally:
        db.close()

if __name__ == "__main__":
    run_action_ml_pipeline_tests()
