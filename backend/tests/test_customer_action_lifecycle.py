from datetime import datetime, timezone, timedelta
from app.db.session import SessionLocal
from app.db.models import Customer, Payment, RecoveryCase, AgentRun, RecoveryAction, AuditEvent, Policy
from app.services.execution_service import execution_service
from app.services.scheduler_service import scheduler_service
from app.services.notification_service import notification_service
from app.policies.guardrails import policy_engine

import uuid

def get_test_db():
    return SessionLocal()

def test_scenario_1_insufficient_funds_customer_action_required(db):
    """Scenario 1: INSUFFICIENT_FUNDS payment failure triggers CUSTOMER_ACTION_REQUIRED state."""
    uid = uuid.uuid4().hex[:8]
    cust = Customer(external_customer_id=f"ext_c1_{uid}", name="Test Customer 1", email=f"cust1_{uid}@example.com", opted_out=False)
    db.add(cust)
    db.commit()

    pay = Payment(
        customer_id=cust.id,
        gateway_payment_id=f"pay_test_s1_{uid}",
        amount=150.0,
        currency="USD",
        status="FAILED",
        failure_reason="INSUFFICIENT_FUNDS",
        failure_category="INSUFFICIENT_FUNDS",
        attempt_number=1
    )
    db.add(pay)
    db.commit()

    case = RecoveryCase(
        payment_id=pay.id,
        customer_id=cust.id,
        status="OPEN",
        revenue_at_risk=150.0,
        recovery_probability=0.75,
        expected_recovery=112.5,
        priority_score=112.5,
        root_cause="CUSTOMER_ACTION",
        root_cause_confidence=0.9,
        recommended_action="CUSTOMER_NUDGE",
        agent_confidence=0.85
    )
    db.add(case)
    db.commit()

    run = AgentRun(case_id=case.id, trigger_type="AUTOMATIC", status="PENDING")
    db.add(run)
    db.commit()

    execution_service.run_agent_workflow_sync(run.id)
    db.refresh(case)

    assert case.status == "CUSTOMER_ACTION_REQUIRED"
    assert case.customer_action_required is True
    assert case.customer_action_type == "ADD_FUNDS"
    assert case.customer_action_status == "PENDING"
    assert case.next_action == "WAIT_FOR_CUSTOMER_ACTION"


def test_scenario_2_customer_fixes_issue_triggers_successful_recovery(db):
    """Scenario 2: Customer completes required action -> re-evaluates -> retry SUCCESS -> RECOVERED."""
    uid = uuid.uuid4().hex[:8]
    cust = Customer(external_customer_id=f"ext_c2_{uid}", name="Test Customer 2", email=f"cust2_{uid}@example.com", opted_out=False)
    db.add(cust)
    db.commit()

    pay = Payment(
        customer_id=cust.id,
        gateway_payment_id=f"pay_test_s2_{uid}",
        amount=200.0,
        currency="USD",
        status="FAILED",
        failure_reason="INSUFFICIENT_FUNDS",
        failure_category="INSUFFICIENT_FUNDS",
        attempt_number=1
    )
    db.add(pay)
    db.commit()

    case = RecoveryCase(
        payment_id=pay.id,
        customer_id=cust.id,
        status="CUSTOMER_ACTION_REQUIRED",
        revenue_at_risk=200.0,
        recovery_probability=0.8,
        expected_recovery=160.0,
        priority_score=160.0,
        root_cause="CUSTOMER_ACTION",
        customer_action_required=True,
        customer_action_type="ADD_FUNDS",
        customer_action_status="PENDING",
        recommended_action="RETRY"
    )
    db.add(case)
    db.commit()

    # Simulate customer completed action
    case.customer_action_status = "COMPLETED"
    db.commit()

    run = AgentRun(case_id=case.id, trigger_type="MANUAL_EXECUTE", recommended_action="RETRY", status="PENDING")
    db.add(run)
    db.commit()

    execution_service.run_agent_workflow_sync(run.id)
    db.refresh(case)
    db.refresh(pay)

    assert pay.status == "SUCCESS"
    assert case.status == "RECOVERED"
    assert case.next_action == "NONE"


def test_scenario_3_customer_does_not_fix_issue_expiration(db):
    """Scenario 3: Expiration window elapses -> STOPPED (CUSTOMER_ACTION_WINDOW_EXPIRED)."""
    uid = uuid.uuid4().hex[:8]
    cust = Customer(external_customer_id=f"ext_c3_{uid}", name="Test Customer 3", email=f"cust3_{uid}@example.com", opted_out=False)
    db.add(cust)
    db.commit()

    pay = Payment(customer_id=cust.id, gateway_payment_id=f"pay_test_s3_{uid}", amount=300.0, status="FAILED", failure_reason="EXPIRED_CARD")
    db.add(pay)
    db.commit()

    now = datetime.now(timezone.utc)
    case = RecoveryCase(
        payment_id=pay.id,
        customer_id=cust.id,
        status="CUSTOMER_ACTION_REQUIRED",
        revenue_at_risk=300.0,
        customer_action_required=True,
        customer_action_type="UPDATE_CARD",
        customer_action_status="PENDING",
        waiting_since=now - timedelta(hours=80),
        retry_after=now - timedelta(hours=50),
        expires_at=now - timedelta(hours=8)
    )
    db.add(case)
    db.commit()

    res = scheduler_service.process_customer_action_lifecycle(db)
    db.refresh(case)

    assert res["expired_cases"] >= 1
    assert case.status == "STOPPED"
    assert case.customer_action_status == "EXPIRED"
    assert case.next_action == "NONE"


def test_scenario_4_customer_event_before_timer(db):
    """Scenario 4: Customer event before timer triggers immediate re-evaluation and recovery."""
    uid = uuid.uuid4().hex[:8]
    cust = Customer(external_customer_id=f"ext_c4_{uid}", name="Test Customer 4", email=f"cust4_{uid}@example.com", opted_out=False)
    db.add(cust)
    db.commit()

    pay = Payment(customer_id=cust.id, gateway_payment_id=f"pay_test_s4_{uid}", amount=400.0, status="FAILED", failure_reason="AUTHENTICATION_REQUIRED")
    db.add(pay)
    db.commit()

    case = RecoveryCase(
        payment_id=pay.id,
        customer_id=cust.id,
        status="CUSTOMER_ACTION_REQUIRED",
        revenue_at_risk=400.0,
        customer_action_required=True,
        customer_action_type="COMPLETE_AUTHENTICATION",
        customer_action_status="PENDING",
        recommended_action="RETRY"
    )
    db.add(case)
    db.commit()

    # Customer completes authentication
    case.customer_action_status = "COMPLETED"
    db.commit()

    run = AgentRun(case_id=case.id, trigger_type="MANUAL_EXECUTE", recommended_action="RETRY", status="PENDING")
    db.add(run)
    db.commit()

    execution_service.run_agent_workflow_sync(run.id)
    db.refresh(case)
    db.refresh(pay)

    assert pay.status == "SUCCESS"
    assert case.status == "RECOVERED"


def test_scenario_5_human_review_separation(db):
    """Scenario 5: HUMAN_REVIEW routes to ESCALATED and remains separate from customer action."""
    uid = uuid.uuid4().hex[:8]
    cust = Customer(external_customer_id=f"ext_c5_{uid}", name="Test Customer 5", email=f"cust5_{uid}@example.com", opted_out=False)
    db.add(cust)
    db.commit()

    pay = Payment(customer_id=cust.id, gateway_payment_id=f"pay_test_s5_{uid}", amount=5000.0, status="FAILED", failure_reason="HIGH_RISK_SUSPICIOUS")
    db.add(pay)
    db.commit()

    case = RecoveryCase(
        payment_id=pay.id,
        customer_id=cust.id,
        status="OPEN",
        revenue_at_risk=5000.0,
        root_cause="RISK_RELATED",
        recommended_action="HUMAN_REVIEW"
    )
    db.add(case)
    db.commit()

    run = AgentRun(case_id=case.id, trigger_type="AUTOMATIC", recommended_action="HUMAN_REVIEW", status="PENDING")
    db.add(run)
    db.commit()

    execution_service.run_agent_workflow_sync(run.id)
    db.refresh(case)

    assert case.status == "ESCALATED"
    assert case.next_action == "HUMAN_REVIEW"
    assert case.customer_action_required is False


def test_scenario_6_opted_out_customer_notification_blocked(db):
    """Scenario 6: Opted-out customer blocks automated notifications and records audit trail."""
    uid = uuid.uuid4().hex[:8]
    cust = Customer(external_customer_id=f"ext_c6_{uid}", name="Test Customer 6", email=f"cust6_{uid}@example.com", opted_out=True)
    db.add(cust)
    db.commit()

    pay = Payment(customer_id=cust.id, gateway_payment_id=f"pay_test_s6_{uid}", amount=250.0, status="FAILED", failure_reason="INSUFFICIENT_FUNDS")
    db.add(pay)
    db.commit()

    case = RecoveryCase(
        payment_id=pay.id,
        customer_id=cust.id,
        status="OPEN",
        revenue_at_risk=250.0,
        root_cause="CUSTOMER_ACTION",
        recommended_action="CUSTOMER_NUDGE"
    )
    db.add(case)
    db.commit()

    # Test direct notification service opt-out enforcement
    notif = notification_service.send_notification(db, case.id, cust.id, "CUSTOMER_ACTION_REQUIRED")
    assert notif.status == "BLOCKED"

    # Also run workflow to verify guardrail policy enforcement
    run = AgentRun(case_id=case.id, trigger_type="AUTOMATIC", recommended_action="CUSTOMER_NUDGE", status="PENDING")
    db.add(run)
    db.commit()

    execution_service.run_agent_workflow_sync(run.id)

    fresh_session = get_test_db()
    audit_blocked = fresh_session.query(AuditEvent).filter(
        AuditEvent.case_id == case.id,
        AuditEvent.event_type.in_(["NOTIFICATION_BLOCKED", "GUARDRAIL_CHECK"])
    ).first()
    assert audit_blocked is not None
    assert "Customer opted out" in audit_blocked.description
    fresh_session.close()


def test_scenario_7_terminal_state_invariant_lock(db):
    """Scenario 7: Payment SUCCESS enforces RECOVERED terminal state; further executions blocked."""
    uid = uuid.uuid4().hex[:8]
    cust = Customer(external_customer_id=f"ext_c7_{uid}", name="Test Customer 7", email=f"cust7_{uid}@example.com", opted_out=False)
    db.add(cust)
    db.commit()

    pay = Payment(customer_id=cust.id, gateway_payment_id=f"pay_test_s7_{uid}", amount=180.0, status="SUCCESS")
    db.add(pay)
    db.commit()

    case = RecoveryCase(
        payment_id=pay.id,
        customer_id=cust.id,
        status="RECOVERED",
        revenue_at_risk=180.0,
        recommended_action="RETRY",
        next_action="NONE"
    )
    db.add(case)
    db.commit()

    allowed, reason, checks = policy_engine.validate_action(db, case, "RETRY")
    assert allowed is False
    assert "already resolved as SUCCESS" in reason


def test_scenario_8_duplicate_scheduler_execution_protection(db):
    """Scenario 8: Duplicate re-evaluation checks active runs to avoid duplicate gateway executions."""
    uid = uuid.uuid4().hex[:8]
    cust = Customer(external_customer_id=f"ext_c8_{uid}", name="Test Customer 8", email=f"cust8_{uid}@example.com", opted_out=False)
    db.add(cust)
    db.commit()

    pay = Payment(customer_id=cust.id, gateway_payment_id=f"pay_test_s8_{uid}", amount=220.0, status="FAILED", failure_reason="INSUFFICIENT_FUNDS")
    db.add(pay)
    db.commit()

    now = datetime.now(timezone.utc)
    case = RecoveryCase(
        payment_id=pay.id,
        customer_id=cust.id,
        status="CUSTOMER_ACTION_REQUIRED",
        revenue_at_risk=220.0,
        customer_action_required=True,
        customer_action_type="ADD_FUNDS",
        customer_action_status="PENDING",
        retry_after=now - timedelta(hours=1),
        expires_at=now + timedelta(hours=24)
    )
    db.add(case)
    db.commit()

    # Add an active run
    run_in_progress = AgentRun(case_id=case.id, status="RUNNING", trigger_type="AUTOMATIC")
    db.add(run_in_progress)
    db.commit()

    res = scheduler_service.process_customer_action_lifecycle(db)
    assert res["skipped_cases"] >= 1


def test_scenario_9_external_payment_success_while_waiting(db):
    """Scenario 9: External payment success while waiting updates case to RECOVERED and cancels waiting."""
    uid = uuid.uuid4().hex[:8]
    cust = Customer(external_customer_id=f"ext_c9_{uid}", name="Test Customer 9", email=f"cust9_{uid}@example.com", opted_out=False)
    db.add(cust)
    db.commit()

    pay = Payment(customer_id=cust.id, gateway_payment_id=f"pay_test_s9_{uid}", amount=350.0, status="FAILED", failure_reason="INSUFFICIENT_FUNDS")
    db.add(pay)
    db.commit()

    case = RecoveryCase(
        payment_id=pay.id,
        customer_id=cust.id,
        status="CUSTOMER_ACTION_REQUIRED",
        revenue_at_risk=350.0,
        customer_action_required=True,
        customer_action_status="PENDING"
    )
    db.add(case)
    db.commit()

    # Payment succeeds externally (e.g. customer paid directly via merchant app)
    pay.status = "SUCCESS"
    db.commit()

    res = scheduler_service.process_customer_action_lifecycle(db)
    db.refresh(case)

    assert case.status == "RECOVERED"
    assert case.customer_action_status == "CANCELLED"
    assert case.next_action == "NONE"


def test_scenario_10_human_approval_followed_by_successful_retry(db):
    """Scenario 10: Operations team approves ESCALATED case -> RETRY executes -> gateway SUCCESS -> RECOVERED."""
    uid = uuid.uuid4().hex[:8]
    cust = Customer(external_customer_id=f"ext_c10_{uid}", name="Test Customer 10", email=f"cust10_{uid}@example.com", opted_out=False)
    db.add(cust)
    db.commit()

    pay = Payment(customer_id=cust.id, gateway_payment_id=f"pay_test_s10_{uid}", amount=600.0, status="FAILED", failure_reason="HIGH_VALUE_CHECK")
    db.add(pay)
    db.commit()

    case = RecoveryCase(
        payment_id=pay.id,
        customer_id=cust.id,
        status="ESCALATED",
        revenue_at_risk=600.0,
        recommended_action="RETRY",
        next_action="HUMAN_REVIEW"
    )
    db.add(case)
    db.commit()

    run = AgentRun(
        case_id=case.id,
        status="PENDING",
        trigger_type="MANUAL_APPROVE",
        recommended_action="RETRY",
        approved=True,
        approved_by="OPS_USER"
    )
    db.add(run)
    db.commit()

    execution_service.run_agent_workflow_sync(run.id)
    db.refresh(case)
    db.refresh(pay)

    assert pay.status == "SUCCESS"
    assert case.status == "RECOVERED"
    assert case.next_action == "NONE"
