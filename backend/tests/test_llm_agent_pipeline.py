import os
import sys
import json
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, 'backend')
from app.config import settings
from app.db.session import engine, SessionLocal, Base
from app.db.models import Customer, Payment, RecoveryCase, Policy, AgentRun, RecoveryAction, AuditEvent
from app.agents.recovery_agent import recovery_agent
from app.policies.guardrails import policy_engine
from app.services.execution_service import execution_service

Base.metadata.create_all(bind=engine)


def run_llm_agent_tests():
    print("================================================================")
    print("   RECOVERAI — LLM RECOVERY AGENT PIPELINE INTEGRATION TEST     ")
    print("================================================================")
    
    db = SessionLocal()
    try:
        # TEST 1: Live LLM Decision Request for Transient Failure
        print("\n----------------------------------------------------------------")
        print(" TEST 1: Transient Failure Live LLM Agent Decision")
        print("----------------------------------------------------------------")
        
        # Create test customer & payment
        cust1 = Customer(external_customer_id="SIM_LLM_CUST_1", name="LLM Test Customer", email="llm.test@example.com", lifetime_value=1250.0, opted_out=False)
        db.add(cust1)
        db.flush()

        pay1 = Payment(gateway_payment_id="pay_llm_001", customer_id=cust1.id, amount=149.00, currency="USD", status="FAILED", failure_reason="NETWORK_TIMEOUT", failure_category="TRANSIENT_FAILURE", attempt_number=1)
        db.add(pay1)
        db.flush()

        case1 = RecoveryCase(
            payment_id=pay1.id,
            customer_id=cust1.id,
            status="OPEN",
            revenue_at_risk=149.00,
            recovery_probability=0.82,
            expected_recovery=122.18,
            priority_score=122.18,
            root_cause="TRANSIENT_FAILURE",
            root_cause_confidence=0.88,
            retry_count=0
        )
        db.add(case1)
        db.commit()

        eval1 = recovery_agent.evaluate_case_full(db, case1)
        print(f" LLM Used           : {eval1.get('llm_used')}")
        print(f" Model              : {eval1.get('model')}")
        print(f" Recommended Action : {eval1.get('recommended_action')}")
        print(f" Reason             : {eval1.get('reason')}")
        print(f" Confidence         : {eval1.get('confidence')}")
        print(f" Risk Assessment    : {eval1.get('risk_assessment')}")
        print(f" Supporting Factors : {eval1.get('supporting_factors')}")

        assert eval1.get('llm_used') is True, "Expected LLM to be used for decision making!"
        assert eval1.get('recommended_action') in ["RETRY", "CUSTOMER_NUDGE", "HUMAN_REVIEW", "STOP"]
        print(" >>> TEST 1 PASSED: Live Mistral LLM decision executed cleanly!")

        # TEST 2: Customer Opted Out Guardrail Safety
        print("\n----------------------------------------------------------------")
        print(" TEST 2: Customer Opted-Out Policy Guardrail Safety")
        print("----------------------------------------------------------------")
        cust2 = Customer(external_customer_id="SIM_LLM_CUST_OPT_OUT", name="Opted Out Customer", email="optout@example.com", lifetime_value=2500.0, opted_out=True)
        db.add(cust2)
        db.flush()

        pay2 = Payment(gateway_payment_id="pay_llm_optout", customer_id=cust2.id, amount=299.00, currency="USD", status="FAILED", failure_reason="CARD_EXPIRED", failure_category="CUSTOMER_ACTION")
        db.add(pay2)
        db.flush()

        case2 = RecoveryCase(payment_id=pay2.id, customer_id=cust2.id, status="OPEN", revenue_at_risk=299.00, recovery_probability=0.75, expected_recovery=224.25, priority_score=224.25, root_cause="CUSTOMER_ACTION", retry_count=0)
        db.add(case2)
        db.commit()

        allowed2, reason2, checks2 = policy_engine.validate_action(db, case2, "RETRY")
        print(f" Guardrail Validation: Allowed={allowed2} | Reason={reason2}")
        assert allowed2 is False, "Expected guardrails to block action for opted-out customer!"
        assert checks2["customer_opt_out"]["passed"] is False
        print(" >>> TEST 2 PASSED: Guardrail blocked action for opted-out customer!")

        # TEST 3: Retry Limit Guardrail Enforcement
        print("\n----------------------------------------------------------------")
        print(" TEST 3: Maximum Retry Limit Exceeded Guardrail Safety")
        print("----------------------------------------------------------------")
        case3 = RecoveryCase(payment_id=pay1.id, customer_id=cust1.id, status="OPEN", revenue_at_risk=149.00, recovery_probability=0.82, expected_recovery=122.18, priority_score=122.18, root_cause="TRANSIENT_FAILURE", retry_count=3)
        allowed3, reason3, checks3 = policy_engine.validate_action(db, case3, "RETRY")
        print(f" Guardrail Validation: Allowed={allowed3} | Reason={reason3}")
        assert allowed3 is False, "Expected guardrails to block retry when retry_count >= max_retries!"
        assert checks3["retry_limit"]["passed"] is False
        print(" >>> TEST 3 PASSED: Guardrail enforced max retry limit!")

        # TEST 4: High-Value Transaction Limit Enforcement
        print("\n----------------------------------------------------------------")
        print(" TEST 4: High-Value Transaction (> $10,000) Guardrail Safety")
        print("----------------------------------------------------------------")
        case4 = RecoveryCase(payment_id=pay1.id, customer_id=cust1.id, status="OPEN", revenue_at_risk=15000.00, recovery_probability=0.90, expected_recovery=13500.00, priority_score=13500.00, root_cause="TRANSIENT_FAILURE", retry_count=0)
        allowed4, reason4, checks4 = policy_engine.validate_action(db, case4, "RETRY")
        print(f" Guardrail Validation: Allowed={allowed4} | Reason={reason4}")
        assert allowed4 is False, "Expected guardrails to block auto-retry for amount > $10,000!"
        assert checks4["max_auto_retry_amount"]["passed"] is False
        print(" >>> TEST 4 PASSED: Guardrail blocked high-value auto-retry!")

        # TEST 5: Fallback to Rule Engine on LLM API Failure / Missing Key
        print("\n----------------------------------------------------------------")
        print(" TEST 5: Fallback Mechanism on LLM API Failure")
        print("----------------------------------------------------------------")
        saved_key = settings.MISTRAL_API_KEY
        settings.MISTRAL_API_KEY = ""
        eval_fallback = recovery_agent.evaluate_case_full(db, case1)
        settings.MISTRAL_API_KEY = saved_key

        print(f" LLM Used           : {eval_fallback.get('llm_used')}")
        print(f" Model              : {eval_fallback.get('model')}")
        print(f" Recommended Action : {eval_fallback.get('recommended_action')}")
        print(f" Reason             : {eval_fallback.get('reason')}")
        assert eval_fallback.get('llm_used') is False
        assert eval_fallback.get('model') == "rule_based_fallback"
        print(" >>> TEST 5 PASSED: Rule-based fallback executed cleanly on missing API key!")

        # TEST 6: Full Workflow Execution & DB Persistence
        print("\n----------------------------------------------------------------")
        print(" TEST 6: Complete Agent Workflow Execution & Database Updates")
        print("----------------------------------------------------------------")
        agent_run = AgentRun(case_id=case1.id, trigger_type="AUTOMATIC")
        db.add(agent_run)
        db.commit()
        db.refresh(agent_run)

        res_run = execution_service.run_agent_workflow_sync(agent_run.id)
        
        # Verify DB updates
        pay1_updated = db.query(Payment).filter(Payment.id == pay1.id).first()
        case1_updated = db.query(RecoveryCase).filter(RecoveryCase.id == case1.id).first()
        actions1 = db.query(RecoveryAction).filter(RecoveryAction.case_id == case1.id).all()
        audits1 = db.query(AuditEvent).filter(AuditEvent.case_id == case1.id).all()

        print(f" Agent Run Status   : {res_run.status}")
        print(f" Final Case Status  : {case1_updated.status}")
        print(f" Payment Status     : {pay1_updated.status}")
        print(f" Action Records     : {len(actions1)}")
        print(f" Audit Events       : {len(audits1)}")

        assert res_run.status == "COMPLETED"
        assert case1_updated.status in ["RECOVERED", "RE_EVALUATING", "STOPPED", "ESCALATED"]
        print(" >>> TEST 6 PASSED: Database state updated and workflow persisted!")

        print("\n================================================================")
        print("   ALL 6 LLM RECOVERY AGENT PIPELINE TESTS PASSED SUCCESSFULLY! ")
        print("================================================================")

    finally:
        db.close()


if __name__ == "__main__":
    run_llm_agent_tests()
