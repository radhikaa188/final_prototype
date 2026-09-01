import os
import uuid
import pytest
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from os.path import dirname, abspath, join

from app.db.models import Payment, RecoveryCase, RecoveryAction, AgentRun, AuditEvent, Customer
from app.services.execution_service import execution_service

BACKEND_DIR = dirname(dirname(abspath(__file__)))
ROOT_DIR = dirname(BACKEND_DIR)
PROD_DB_PATH = join(ROOT_DIR, "recoverai.db")
PROD_DB_URL = f"sqlite:///{PROD_DB_PATH}"

prod_engine = create_engine(PROD_DB_URL, connect_args={"check_same_thread": False})
ProdSession = sessionmaker(autocommit=False, autoflush=False, bind=prod_engine)

def get_prod_db_metrics():
    with ProdSession() as prod_db:
        p_count = prod_db.query(Payment).count()
        c_count = prod_db.query(RecoveryCase).count()
        c_recovered = prod_db.query(RecoveryCase).filter(RecoveryCase.status == "RECOVERED").count()
        a_count = prod_db.query(RecoveryAction).count()
        a_revenue = prod_db.query(func.sum(RecoveryAction.amount_recovered)).filter(RecoveryAction.status == "SUCCESS").scalar() or 0.0
        r_count = prod_db.query(AgentRun).count()
        e_count = prod_db.query(AuditEvent).count()
        return {
            "payments": p_count,
            "cases": c_count,
            "recovered_cases": c_recovered,
            "actions": a_count,
            "revenue": float(a_revenue),
            "agent_runs": r_count,
            "audit_events": e_count
        }

def test_tests_do_not_modify_application_database(db):
    """
    Explicit Contamination Test:
    1. Records snapshot of all metric counts in the real application database (recoverai.db).
    2. Executes a complete simulated recovery and commits records into the test session (db).
    3. Reads application DB snapshot again.
    4. Asserts that EVERY metric in the real application DB is 100% unchanged (Delta = 0).
    5. Asserts that the test database received and committed the records properly.
    """
    before_metrics = get_prod_db_metrics()

    # Create test records in isolated test session
    uid = uuid.uuid4().hex[:8]
    cust = Customer(external_customer_id=f"ext_iso_{uid}", name="Isolation Test Customer", email=f"iso_{uid}@example.com")
    db.add(cust)
    db.commit()

    pay = Payment(
        customer_id=cust.id,
        gateway_payment_id=f"pay_test_iso_{uid}",
        amount=999.0,
        currency="USD",
        status="FAILED",
        failure_reason="INSUFFICIENT_FUNDS",
        attempt_number=1
    )
    db.add(pay)
    db.commit()

    case = RecoveryCase(
        payment_id=pay.id,
        customer_id=cust.id,
        status="OPEN",
        revenue_at_risk=999.0,
        recommended_action="RETRY"
    )
    db.add(case)
    db.commit()

    # Execute retry through execution_service in the isolated test DB
    run = AgentRun(case_id=case.id, trigger_type="AUTOMATIC", status="PENDING")
    db.add(run)
    db.commit()

    completed_run = execution_service.run_agent_workflow_sync(run.id)

    # Assert test session has the records
    assert completed_run is not None
    assert completed_run.status in ("COMPLETED", "RUNNING")
    assert db.query(Payment).filter(Payment.gateway_payment_id == f"pay_test_iso_{uid}").first() is not None

    # Read production DB metrics again
    after_metrics = get_prod_db_metrics()

    # Assert zero change in production DB
    for key, val in before_metrics.items():
        assert after_metrics[key] == val, f"Contamination detected in production DB! Metric '{key}' changed from {val} to {after_metrics[key]}"
