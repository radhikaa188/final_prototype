from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.db.models import RecoveryCase, Payment, AgentRun
from app.services.audit_service import audit_service
from app.services.notification_service import notification_service
from app.services.execution_service import execution_service

class SchedulerService:
    @staticmethod
    def process_customer_action_lifecycle(db: Session) -> dict:
        """
        Scans all recovery cases in CUSTOMER_ACTION_REQUIRED state to handle:
        1. Expiration (expires_at <= current_time and customer_action_status == PENDING) -> STOPPED
        2. Scheduled Re-evaluation (retry_after <= current_time and expires_at > current_time and customer_action_status == PENDING)
        """
        now = datetime.now(timezone.utc)
        
        expired_count = 0
        reevaluated_count = 0
        skipped_count = 0

        # Query all active customer action required cases
        cases = db.query(RecoveryCase).filter(
            RecoveryCase.status == "CUSTOMER_ACTION_REQUIRED"
        ).all()

        for case in cases:
            # First check payment status invariant
            payment = db.query(Payment).filter(Payment.id == case.payment_id).first()
            if payment and payment.status == "SUCCESS":
                case.status = "RECOVERED"
                case.customer_action_status = "CANCELLED"
                case.next_action = "NONE"
                case.closed_at = now
                audit_service.record_event(
                    db,
                    "PAYMENT_SUCCESS_OBSERVED",
                    "SYSTEM",
                    f"External payment success detected while waiting for customer action. Case marked RECOVERED.",
                    case_id=case.id
                )
                db.commit()
                skipped_count += 1
                continue

            # Ensure timezone compatibility
            expires_at = case.expires_at
            if expires_at and expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
                
            retry_after = case.retry_after
            if retry_after and retry_after.tzinfo is None:
                retry_after = retry_after.replace(tzinfo=timezone.utc)

            # 1. Expiration Check
            if expires_at and now >= expires_at and case.customer_action_status == "PENDING":
                case.status = "STOPPED"
                case.customer_action_status = "EXPIRED"
                case.next_action = "NONE"
                case.closed_at = now
                
                audit_service.record_event(
                    db,
                    "CUSTOMER_ACTION_WINDOW_EXPIRED",
                    "SYSTEM",
                    f"Customer action window expired at {expires_at.isoformat()}. Automated recovery halted.",
                    case_id=case.id
                )
                notification_service.send_notification(
                    db,
                    case.id,
                    case.customer_id,
                    "RECOVERY_STOPPED",
                    reason="Customer action window expired"
                )
                db.commit()
                expired_count += 1

            # 2. Scheduled Re-evaluation Check
            elif (retry_after and now >= retry_after and (not expires_at or now < expires_at) 
                  and case.customer_action_status in ["PENDING", "COMPLETED"]):
                
                # Idempotency Check: Verify no active run is in progress
                active_run = db.query(AgentRun).filter(
                    AgentRun.case_id == case.id,
                    AgentRun.status.in_(["PENDING", "RUNNING"])
                ).first()

                if active_run:
                    skipped_count += 1
                    continue

                # Create and execute new agent run for re-evaluation
                audit_service.record_event(
                    db,
                    "RE-EVALUATION STARTED",
                    "SYSTEM",
                    f"Scheduled re-evaluation triggered after wait period expired.",
                    case_id=case.id
                )

                new_run = AgentRun(
                    case_id=case.id,
                    trigger_type="AUTOMATIC",
                    status="PENDING"
                )
                db.add(new_run)
                db.commit()
                db.refresh(new_run)

                execution_service.run_agent_workflow_sync(new_run.id)
                reevaluated_count += 1

        return {
            "expired_cases": expired_count,
            "reevaluated_cases": reevaluated_count,
            "skipped_cases": skipped_count,
            "total_processed": len(cases)
        }

scheduler_service = SchedulerService()
