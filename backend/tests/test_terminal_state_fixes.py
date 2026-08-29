import sys
from datetime import datetime
from fastapi.testclient import TestClient

sys.path.insert(0, 'backend')
from app.main import app
from app.db.session import engine, SessionLocal, Base
from app.db.models import Customer, Payment, RecoveryCase, AgentRun, RecoveryAction, AuditEvent
from app.services.execution_service import execution_service

client = TestClient(app)

def run_terminal_state_fix_tests():
    print("=========================================================================")
    print("    RECOVERAI — TERMINAL STATE PROTECTION & API GUARDS TEST SUITE      ")
    print("=========================================================================")

    db = SessionLocal()
    try:
        uid = datetime.now().strftime("%H%M%S")

        # Create test customer and failed payment
        cust = Customer(
            external_customer_id=f"TERM_CUST_{uid}",
            name="Terminal State Test Customer",
            email=f"term_{uid}@example.com",
            lifetime_value=1200.0,
            opted_out=False
        )
        db.add(cust)
        db.flush()

        pay = Payment(
            gateway_payment_id=f"pay_term_{uid}",
            customer_id=cust.id,
            amount=99.00,
            currency="USD",
            status="FAILED",
            failure_reason="NETWORK_TIMEOUT",
            attempt_number=1
        )
        db.add(pay)
        db.flush()

        case = RecoveryCase(
            payment_id=pay.id,
            customer_id=cust.id,
            status="OPEN",
            revenue_at_risk=99.00,
            recovery_probability=0.95,
            expected_recovery=94.05,
            priority_score=94.05,
            root_cause="TRANSIENT_FAILURE",
            retry_count=0
        )
        db.add(case)
        db.commit()

        print("\n-------------------------------------------------------------------------")
        print(" TEST 1: Initial Successful Recovery Workflow Run")
        print("-------------------------------------------------------------------------")
        run1 = AgentRun(case_id=case.id, trigger_type="AUTOMATIC")
        db.add(run1)
        db.commit()

        run1_res = execution_service.run_agent_workflow_sync(run1.id)
        db.refresh(case)
        db.refresh(pay)

        print(f" Run 1 Status    : {run1_res.status}")
        print(f" Payment Status  : {pay.status}")
        print(f" Case Status     : {case.status}")
        print(f" Closed At       : {case.closed_at}")

        assert run1_res.status == "COMPLETED"
        assert pay.status == "SUCCESS"
        assert case.status == "RECOVERED"
        assert case.closed_at is not None
        print(" >>> TEST 1 PASSED: Case successfully recovered!")

        print("\n-------------------------------------------------------------------------")
        print(" TEST 2: Second Agent Run on RECOVERED Case (Guardrail Blocks & Preserves Actions)")
        print("-------------------------------------------------------------------------")
        initial_action = case.recommended_action
        # Manually create a 2nd run to simulate re-running on a RECOVERED case
        run2 = AgentRun(case_id=case.id, trigger_type="AUTOMATIC")
        db.add(run2)
        db.commit()

        # Run workflow synchronously
        run2_res = execution_service.run_agent_workflow_sync(run2.id)
        db.refresh(case)

        print(f" Run 2 Status           : {run2_res.status}")
        print(f" Case Status            : {case.status} (Must stay RECOVERED, not STOPPED)")
        print(f" Case RecommendedAction : {case.recommended_action} (Must stay {initial_action})")
        print(f" Case NextAction        : {case.next_action} (Must stay NONE)")

        # CRITICAL ASSERTIONS: case.status and case.recommended_action must NOT be overwritten!
        assert case.status == "RECOVERED", f"Case status should remain RECOVERED, got {case.status}"
        assert case.recommended_action == initial_action, f"Recommended action should remain {initial_action}, got {case.recommended_action}"
        assert case.next_action == "NONE", f"Next action should remain NONE, got {case.next_action}"
        print(" >>> TEST 2 PASSED: Guardrail block did NOT overwrite terminal RECOVERED status or recommended action!")

        print("\n-------------------------------------------------------------------------")
        print(" TEST 3: Terminal Run Early Exit (Prevents Re-Running Steps)")
        print("-------------------------------------------------------------------------")
        # Attempt to run the already COMPLETED run1 again
        run1_again = execution_service.run_agent_workflow_sync(run1.id)
        assert run1_again.status == "COMPLETED"
        print(" >>> TEST 3 PASSED: Completed run early exited cleanly!")

        print("\n-------------------------------------------------------------------------")
        print(" TEST 4: API Endpoint Protection (POST /approve, /execute, /escalate)")
        print("-------------------------------------------------------------------------")
        res_approve = client.post(f"/api/recovery-cases/{case.id}/approve")
        print(f" Approve Status Code : {res_approve.status_code} | Detail: {res_approve.json().get('detail')}")
        assert res_approve.status_code == 400
        assert "already recovered" in res_approve.json()["detail"].lower()

        res_execute = client.post(f"/api/recovery-cases/{case.id}/execute")
        print(f" Execute Status Code : {res_execute.status_code} | Detail: {res_execute.json().get('detail')}")
        assert res_execute.status_code == 400
        assert "already recovered" in res_execute.json()["detail"].lower()

        res_escalate = client.post(f"/api/recovery-cases/{case.id}/escalate")
        print(f" Escalate Status Code: {res_escalate.status_code} | Detail: {res_escalate.json().get('detail')}")
        assert res_escalate.status_code == 400
        assert "already recovered" in res_escalate.json()["detail"].lower()

        print(" >>> TEST 4 PASSED: All API endpoints correctly returned 400 for RECOVERED case!")

        print("\n=========================================================================")
        print("    ALL TERMINAL STATE PROTECTION & API GUARD TESTS PASSED SUCCESSFULLY! ")
        print("=========================================================================")

    finally:
        db.close()

if __name__ == "__main__":
    run_terminal_state_fix_tests()
