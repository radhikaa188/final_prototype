import sys
import os
from datetime import timezone

sys.path.insert(0, r"c:\Users\radhi\OneDrive\Desktop\final_prototype\backend")

from app.db.session import SessionLocal
from app.db.models import RecoveryCase, AgentRun, AgentRunStep, RecoveryAction, AuditEvent

def audit_timestamps():
    db = SessionLocal()
    print("=== STARTING HISTORICAL TIMESTAMP AUDIT ===")

    invalid_runs = 0
    invalid_steps = 0
    invalid_cases = 0
    repaired_count = 0
    manual_review_count = 0

    # 1. Audit AgentRuns
    runs = db.query(AgentRun).all()
    for r in runs:
        if r.started_at and r.completed_at:
            # Ensure timezone awareness
            s_at = r.started_at.replace(tzinfo=timezone.utc) if r.started_at.tzinfo is None else r.started_at
            c_at = r.completed_at.replace(tzinfo=timezone.utc) if r.completed_at.tzinfo is None else r.completed_at
            if c_at < s_at:
                print(f"Anomaly in AgentRun {r.id}: completed_at ({c_at}) is before started_at ({s_at})")
                invalid_runs += 1
                manual_review_count += 1

    # 2. Audit AgentRunSteps
    steps = db.query(AgentRunStep).all()
    for s in steps:
        if s.started_at and s.completed_at:
            s_at = s.started_at.replace(tzinfo=timezone.utc) if s.started_at.tzinfo is None else s.started_at
            c_at = s.completed_at.replace(tzinfo=timezone.utc) if s.completed_at.tzinfo is None else s.completed_at
            if c_at < s_at:
                print(f"Anomaly in AgentRunStep {s.id} (Run {s.run_id}): completed_at ({c_at}) is before started_at ({s_at})")
                invalid_steps += 1
                manual_review_count += 1

    # 3. Audit RecoveryCases
    cases = db.query(RecoveryCase).all()
    for case in cases:
        c_at = case.created_at.replace(tzinfo=timezone.utc) if case.created_at.tzinfo is None else case.created_at
        cl_at = case.closed_at.replace(tzinfo=timezone.utc) if case.closed_at and case.closed_at.tzinfo is None else case.closed_at
        
        if cl_at and cl_at < c_at:
            print(f"Anomaly in RecoveryCase {case.id}: closed_at ({cl_at}) is before created_at ({c_at})")
            invalid_cases += 1
            manual_review_count += 1

        # Check customer action expiration bounds
        expires_at = case.expires_at.replace(tzinfo=timezone.utc) if case.expires_at and case.expires_at.tzinfo is None else case.expires_at
        waiting_since = case.waiting_since.replace(tzinfo=timezone.utc) if case.waiting_since and case.waiting_since.tzinfo is None else case.waiting_since
        
        if expires_at and waiting_since and expires_at < waiting_since:
            print(f"Anomaly in RecoveryCase {case.id}: expires_at ({expires_at}) is before waiting_since ({waiting_since})")
            invalid_cases += 1
            manual_review_count += 1

    db.close()

    print("\n=== TIMELINE AUDIT COMPLETE ===")
    print(f"Invalid AgentRuns found       : {invalid_runs}")
    print(f"Invalid AgentRunSteps found   : {invalid_steps}")
    print(f"Invalid RecoveryCases found   : {invalid_cases}")
    print(f"Total anomalies repaired      : {repaired_count}")
    print(f"Total requiring manual review : {manual_review_count}")

if __name__ == "__main__":
    audit_timestamps()
