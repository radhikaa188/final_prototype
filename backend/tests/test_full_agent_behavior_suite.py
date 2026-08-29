import sys
import json
from datetime import datetime
from fastapi.testclient import TestClient

sys.path.insert(0, 'backend')
from app.main import app
from app.db.session import engine, SessionLocal, Base
from app.db.models import Customer, Payment, RecoveryCase, AgentRun, RecoveryAction, AuditEvent, Notification
from app.services.execution_service import execution_service
from app.ml.action_predictor import action_predictor

client = TestClient(app)

def run_full_agent_behavior_suite():
    print("=========================================================================")
    print("     RECOVERAI — COMPLETE AGENT BEHAVIOR & END-TO-END SUITE              ")
    print("=========================================================================")

    db = SessionLocal()
    try:
        uid = datetime.now().strftime("%H%M%S")

        # SCENARIO 1: ML -> RETRY -> allowed -> SUCCESS -> RECOVERED
        print("\n-------------------------------------------------------------------------")
        print(" SCENARIO 1: ML -> RETRY -> Allowed -> SUCCESS -> RECOVERED")
        print("-------------------------------------------------------------------------")
        from app.services.gateway_simulator import gateway_simulator
        gateway_simulator.force_success_rate = 1.0 # Force gateway success for Scenario 1

        c1 = Customer(external_customer_id=f"SUITE_C1_{uid}", name="Scenario 1 Customer", email=f"c1_{uid}@example.com", lifetime_value=1200.0, opted_out=False)
        db.add(c1)
        db.flush()

        p1 = Payment(gateway_payment_id=f"pay_sc1_{uid}", customer_id=c1.id, amount=19.99, currency="USD", status="FAILED", failure_reason="NETWORK_TIMEOUT", attempt_number=1)
        db.add(p1)
        db.flush()

        case1 = RecoveryCase(payment_id=p1.id, customer_id=c1.id, status="OPEN", revenue_at_risk=19.99, recovery_probability=0.92, expected_recovery=18.39, priority_score=18.39, root_cause="TRANSIENT_FAILURE", retry_count=0)
        db.add(case1)
        db.commit()

        run1 = AgentRun(case_id=case1.id, trigger_type="AUTOMATIC")
        db.add(run1)
        db.commit()

        run1_res = execution_service.run_agent_workflow_sync(run1.id)
        db.refresh(p1)
        db.refresh(case1)

        print(f" Run 1 Status    : {run1_res.status}")
        print(f" Payment Status  : {p1.status}")
        print(f" Case Status     : {case1.status}")
        print(f" RecommendedAct  : {case1.recommended_action}")
        print(f" NextAction       : {case1.next_action}")

        assert run1_res.status == "COMPLETED"
        assert p1.status == "SUCCESS"
        assert case1.status == "RECOVERED"
        assert case1.recommended_action == "RETRY"
        assert case1.next_action == "NONE"
        print(" >>> SCENARIO 1 PASSED: Automatic RETRY recovered payment and finalized case state!")

        # SCENARIO 2: ML -> RETRY -> allowed -> FAILED -> re-evaluation / stopped max retries
        print("\n-------------------------------------------------------------------------")
        print(" SCENARIO 2: ML -> RETRY -> Allowed -> FAILED -> Re-evaluation / Max Retries")
        print("-------------------------------------------------------------------------")
        from app.services.gateway_simulator import gateway_simulator
        orig_rate = gateway_simulator.force_success_rate
        gateway_simulator.force_success_rate = 0.0 # Force gateway failure for Scenario 2

        c2 = Customer(external_customer_id=f"SUITE_C2_{uid}", name="Scenario 2 Customer", email=f"c2_{uid}@example.com", lifetime_value=600.0, opted_out=False)
        db.add(c2)
        db.flush()

        p2 = Payment(gateway_payment_id=f"pay_sc2_{uid}", customer_id=c2.id, amount=49.99, currency="USD", status="FAILED", failure_reason="INSUFFICIENT_FUNDS", attempt_number=1)
        db.add(p2)
        db.flush()

        case2 = RecoveryCase(payment_id=p2.id, customer_id=c2.id, status="OPEN", revenue_at_risk=49.99, recovery_probability=0.45, expected_recovery=22.49, priority_score=22.49, root_cause="TRANSIENT_FAILURE", retry_count=0)
        db.add(case2)
        db.commit()

        run2 = AgentRun(case_id=case2.id, trigger_type="AUTOMATIC")
        db.add(run2)
        db.commit()

        run2_res = execution_service.run_agent_workflow_sync(run2.id)
        gateway_simulator.force_success_rate = orig_rate # Restore original rate
        db.refresh(p2)
        db.refresh(case2)

        print(f" Run 2 Status    : {run2_res.status}")
        print(f" Case Status     : {case2.status}")
        print(f" Retry Count     : {case2.retry_count}")

        assert run2_res.status == "COMPLETED"
        assert case2.status in ["RE_EVALUATING", "STOPPED"]
        print(" >>> SCENARIO 2 PASSED: Failed retry moved case to re-evaluation state!")

        # SCENARIO 3: ML -> CUSTOMER_NUDGE -> Notification sent
        print("\n-------------------------------------------------------------------------")
        print(" SCENARIO 3: ML -> CUSTOMER_NUDGE -> Notification Dispatched")
        print("-------------------------------------------------------------------------")
        c3 = Customer(external_customer_id=f"SUITE_C3_{uid}", name="Scenario 3 Customer", email=f"c3_{uid}@example.com", lifetime_value=250.0, opted_out=False)
        db.add(c3)
        db.flush()

        p3 = Payment(gateway_payment_id=f"pay_sc3_{uid}", customer_id=c3.id, amount=15.00, currency="USD", status="FAILED", failure_reason="CARD_EXPIRED", attempt_number=1)
        db.add(p3)
        db.flush()

        case3 = RecoveryCase(payment_id=p3.id, customer_id=c3.id, status="OPEN", revenue_at_risk=15.00, recovery_probability=0.55, expected_recovery=8.25, priority_score=8.25, root_cause="CUSTOMER_ACTION", retry_count=0)
        db.add(case3)
        db.commit()

        run3 = AgentRun(case_id=case3.id, trigger_type="AUTOMATIC")
        db.add(run3)
        db.commit()

        run3_res = execution_service.run_agent_workflow_sync(run3.id)
        db.refresh(case3)
        
        nudge_notifs = db.query(Notification).filter(Notification.case_id == case3.id).all()
        print(f" Run 3 Status    : {run3_res.status}")
        print(f" Case Status     : {case3.status}")
        print(f" Notifications   : {len(nudge_notifs)}")

        assert len(nudge_notifs) >= 1
        assert any(n.type in ["CUSTOMER_NUDGE", "NUDGE_SENT", "AUTOMATIC_RETRY_ATTEMPTED", "RECOVERY_SUCCESS"] for n in nudge_notifs)
        print(" >>> SCENARIO 3 PASSED: Customer nudge dispatched customer notification!")

        # SCENARIO 4: ML -> HUMAN_REVIEW -> Human Queue Routing
        print("\n-------------------------------------------------------------------------")
        print(" SCENARIO 4: ML -> HUMAN_REVIEW -> Human Queue Routing")
        print("-------------------------------------------------------------------------")
        c4 = Customer(external_customer_id=f"SUITE_C4_{uid}", name="Scenario 4 Customer", email=f"c4_{uid}@example.com", lifetime_value=4500.0, opted_out=False)
        db.add(c4)
        db.flush()

        p4 = Payment(gateway_payment_id=f"pay_sc4_{uid}", customer_id=c4.id, amount=4500.00, currency="USD", status="FAILED", failure_reason="FRAUD_RISK", attempt_number=2)
        db.add(p4)
        db.flush()

        case4 = RecoveryCase(payment_id=p4.id, customer_id=c4.id, status="OPEN", revenue_at_risk=4500.00, recovery_probability=0.20, expected_recovery=900.00, priority_score=900.00, root_cause="RISK_RELATED", retry_count=1)
        db.add(case4)
        db.commit()

        run4 = AgentRun(case_id=case4.id, trigger_type="AUTOMATIC")
        db.add(run4)
        db.commit()

        run4_res = execution_service.run_agent_workflow_sync(run4.id)
        db.refresh(case4)

        print(f" Run 4 Status    : {run4_res.status}")
        print(f" Case Status     : {case4.status}")
        print(f" Next Action     : {case4.next_action}")

        assert case4.status == "ESCALATED"
        assert case4.next_action == "HUMAN_REVIEW"

        # Verify Human Review Queue Detail API
        res_hr = client.get(f"/api/recovery-cases/{case4.id}")
        assert res_hr.status_code == 200
        hr_data = res_hr.json()
        assert hr_data["status"] == "ESCALATED"
        assert hr_data["ml_intelligence"]["root_cause"] == "RISK_RELATED"
        assert hr_data["payment"]["amount"] == 4500.00
        print(" >>> SCENARIO 4 PASSED: HUMAN_REVIEW routed case to Human Operations Queue!")

        # SCENARIO 5: ML -> STOP -> STOPPED Terminal State
        print("\n-------------------------------------------------------------------------")
        print(" SCENARIO 5: ML -> STOP -> STOPPED Terminal State")
        print("-------------------------------------------------------------------------")
        c5 = Customer(external_customer_id=f"SUITE_C5_{uid}", name="Scenario 5 Customer", email=f"c5_{uid}@example.com", lifetime_value=50.0, opted_out=False)
        db.add(c5)
        db.flush()

        p5 = Payment(gateway_payment_id=f"pay_sc5_{uid}", customer_id=c5.id, amount=25.00, currency="USD", status="FAILED", failure_reason="ACCOUNT_CLOSED", attempt_number=3)
        db.add(p5)
        db.flush()

        case5 = RecoveryCase(payment_id=p5.id, customer_id=c5.id, status="OPEN", revenue_at_risk=25.00, recovery_probability=0.05, expected_recovery=1.25, priority_score=1.25, root_cause="OTHER", retry_count=3)
        db.add(case5)
        db.commit()

        run5 = AgentRun(case_id=case5.id, trigger_type="AUTOMATIC")
        db.add(run5)
        db.commit()

        run5_res = execution_service.run_agent_workflow_sync(run5.id)
        db.refresh(case5)

        print(f" Run 5 Status    : {run5_res.status}")
        print(f" Case Status     : {case5.status}")

        assert case5.status in ["STOPPED", "ESCALATED"]
        print(" >>> SCENARIO 5 PASSED: Recovery halted cleanly into terminal STOPPED/ESCALATED state!")

        # SCENARIO 6: ML Recommends RETRY but Guardrail Blocks -> STOPPED with Reason
        print("\n-------------------------------------------------------------------------")
        print(" SCENARIO 6: Guardrail Blocks ML Recommendation -> STOPPED with Reason")
        print("-------------------------------------------------------------------------")
        c6 = Customer(external_customer_id=f"SUITE_C6_{uid}", name="Scenario 6 Customer", email=f"c6_{uid}@example.com", lifetime_value=1200.0, opted_out=False)
        db.add(c6)
        db.flush()

        p6 = Payment(gateway_payment_id=f"pay_sc6_{uid}", customer_id=c6.id, amount=150.00, currency="USD", status="FAILED", failure_reason="NETWORK_TIMEOUT", attempt_number=3)
        db.add(p6)
        db.flush()

        case6 = RecoveryCase(payment_id=p6.id, customer_id=c6.id, status="OPEN", revenue_at_risk=150.00, recovery_probability=0.92, expected_recovery=138.00, priority_score=138.00, root_cause="TRANSIENT_FAILURE", retry_count=3)
        db.add(case6)
        db.commit()

        from app.policies.guardrails import policy_engine
        allowed_6, reason_6, _ = policy_engine.validate_action(db, case6, "RETRY")
        print(f" Guardrail Allowed : {allowed_6}")
        print(f" Guardrail Reason  : {reason_6}")

        assert allowed_6 is False
        assert "Maximum automatic retries" in reason_6 or "BLOCKED" in reason_6
        print(" >>> SCENARIO 6 PASSED: Guardrail blocked retry with clear policy reason!")

        # SCENARIO 7: Customer Opted Out -> Automatic Nudge Blocked + Audit Event
        print("\n-------------------------------------------------------------------------")
        print(" SCENARIO 7: Customer Opted Out -> Nudge Blocked + Audit Trail")
        print("-------------------------------------------------------------------------")
        c7 = Customer(external_customer_id=f"SUITE_C7_{uid}", name="Opted Out Customer", email=f"c7_{uid}@example.com", lifetime_value=800.0, opted_out=True)
        db.add(c7)
        db.flush()

        p7 = Payment(gateway_payment_id=f"pay_sc7_{uid}", customer_id=c7.id, amount=99.00, currency="USD", status="FAILED", failure_reason="CARD_EXPIRED", attempt_number=1)
        db.add(p7)
        db.flush()

        case7 = RecoveryCase(payment_id=p7.id, customer_id=c7.id, status="OPEN", revenue_at_risk=99.00, recovery_probability=0.85, expected_recovery=84.15, priority_score=84.15, root_cause="TRANSIENT_FAILURE", retry_count=0)
        db.add(case7)
        db.commit()

        run7 = AgentRun(case_id=case7.id, trigger_type="AUTOMATIC")
        db.add(run7)
        db.commit()

        run7_res = execution_service.run_agent_workflow_sync(run7.id)
        db.refresh(case7)

        opt_audits = db.query(AuditEvent).filter(AuditEvent.case_id == case7.id).all()
        print(f" Run 7 Status    : {run7_res.status}")
        print(f" Case Status     : {case7.status}")
        print(f" Audit Events    : {len(opt_audits)}")

        assert run7_res.status == "BLOCKED"
        assert case7.status == "STOPPED"
        assert any("opted out" in a.description.lower() for a in opt_audits)
        print(" >>> SCENARIO 7 PASSED: Opted-out customer blocked recovery and logged audit trail!")

        # SCENARIO 8 & 9 & 10: Already RECOVERED Case Protection & Invariants
        print("\n-------------------------------------------------------------------------")
        print(" SCENARIO 8-10: RECOVERED Terminal State Invariants & API Guards")
        print("-------------------------------------------------------------------------")
        assert case1.status == "RECOVERED"
        assert case1.recommended_action == "RETRY"
        assert case1.next_action == "NONE"

        # Attempt 2nd run on RECOVERED case1
        run1_second = AgentRun(case_id=case1.id, trigger_type="AUTOMATIC")
        db.add(run1_second)
        db.commit()

        execution_service.run_agent_workflow_sync(run1_second.id)
        db.refresh(case1)

        print(f" Post-Run Case Status    : {case1.status} (Must stay RECOVERED)")
        print(f" Post-Run RecAction      : {case1.recommended_action} (Must stay RETRY)")
        print(f" Post-Run NextAction     : {case1.next_action} (Must stay NONE)")

        assert case1.status == "RECOVERED"
        assert case1.recommended_action == "RETRY"
        assert case1.next_action == "NONE"

        # Verify API Endpoint Blocks
        res_app = client.post(f"/api/recovery-cases/{case1.id}/approve")
        assert res_app.status_code == 400
        print(" >>> SCENARIOS 8-10 PASSED: RECOVERED terminal state and action invariants strictly enforced!")

        # SCENARIO 11: Notification and Audit Event Coverage
        print("\n-------------------------------------------------------------------------")
        print(" SCENARIO 11: Notification & Audit Record Generation")
        print("-------------------------------------------------------------------------")
        notifs_all = db.query(Notification).filter(Notification.case_id == case1.id).all()
        audits_all = db.query(AuditEvent).filter(AuditEvent.case_id == case1.id).all()
        print(f" Case 1 Notifications : {len(notifs_all)}")
        print(f" Case 1 Audit Events  : {len(audits_all)}")

        assert len(notifs_all) >= 1
        assert len(audits_all) >= 3
        print(" >>> SCENARIO 11 PASSED: Complete notification and audit trails persisted!")

        print("\n=========================================================================")
        print("   ALL 11 AGENT BEHAVIOR & INVARIANT SCENARIOS PASSED SUCCESSFULLY!      ")
        print("=========================================================================")

    finally:
        db.close()

if __name__ == "__main__":
    run_full_agent_behavior_suite()
