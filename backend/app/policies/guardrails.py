from datetime import datetime, timezone, timedelta
from typing import Tuple, Dict, Any, List
from sqlalchemy.orm import Session
from app.db.models import Policy, RecoveryCase, Payment, Customer, RecoveryAction

class PolicyEngine:
    @staticmethod
    def get_active_policy(db: Session) -> Policy:
        policy = db.query(Policy).filter(Policy.id == "default_policy").first()
        if not policy:
            policy = Policy(
                id="default_policy",
                max_retries=3,
                recovery_window_hours=72,
                max_auto_retry_amount=10000.0,
                customer_opt_out_enabled=True,
                duplicate_action_protection=True,
                customer_action_wait_hours=24,
                customer_action_expire_hours=72
            )
            db.add(policy)
            db.commit()
            db.refresh(policy)
        return policy

    @staticmethod
    def classify_customer_action_requirement(failure_reason: str, root_cause: str = None) -> Tuple[bool, str, str]:
        """
        Classifies payment decline telemetry to determine if customer intervention is required.
        Returns: (customer_action_required: bool, customer_action_type: str, customer_action_description: str)
        """
        reason_upper = str(failure_reason or "").upper()
        root_upper = str(root_cause or "").upper()

        if "INSUFFICIENT" in reason_upper or "FUNDS" in reason_upper:
            return True, "ADD_FUNDS", "Customer needs to add sufficient funds to their account before payment retry."
        elif "EXPIRED" in reason_upper or "CARD_EXPIRED" in reason_upper:
            return True, "UPDATE_CARD", "Customer needs to update card expiration date or issue a new card."
        elif "INVALID_CARD" in reason_upper or "DO_NOT_HONOR" in reason_upper or ("DECLINED" in reason_upper and root_upper == "CUSTOMER_ACTION"):
            return True, "UPDATE_PAYMENT_METHOD", "Customer needs to update billing method or select another payment card."
        elif "AUTH" in reason_upper or "3DS" in reason_upper or "AUTHENTICATION" in reason_upper:
            return True, "COMPLETE_AUTHENTICATION", "Customer needs to complete 3D-Secure authentication."
        elif "MANDATE" in reason_upper or "AUTHORIZATION" in reason_upper:
            return True, "AUTHORIZE_MANDATE", "Customer needs to re-authorize payment e-mandate."
        elif root_upper == "CUSTOMER_ACTION":
            return True, "OTHER", "Customer action required to resolve payment decline."

        return False, "NONE", "No customer action required."

    @staticmethod
    def validate_action(
        db: Session,
        case: RecoveryCase,
        action_type: str
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Validates an agent's proposed action against operational policies.
        Returns: (is_allowed, reason, guardrail_checks)
        """
        policy = PolicyEngine.get_active_policy(db)
        payment = db.query(Payment).filter(Payment.id == case.payment_id).first()
        customer = db.query(Customer).filter(Customer.id == case.customer_id).first()
        
        checks = {
            "retry_limit": {"passed": True, "details": f"Attempt {case.retry_count} / {policy.max_retries}"},
            "recovery_window": {"passed": True, "details": f"Within {policy.recovery_window_hours}h limit"},
            "max_auto_retry_amount": {"passed": True, "details": f"${case.revenue_at_risk:,.2f} <= ${policy.max_auto_retry_amount:,.2f}"},
            "customer_opt_out": {"passed": True, "details": "Customer active (not opted out)"},
            "duplicate_action": {"passed": True, "details": "Action path clear"},
            "payment_status": {"passed": True, "details": f"Current payment status: {payment.status if payment else 'UNKNOWN'}"}
        }

        # 1. Payment status check
        if payment and payment.status == "SUCCESS":
            checks["payment_status"] = {"passed": False, "details": "Payment is already successful"}
            return False, "BLOCKED: Payment is already resolved as SUCCESS", checks

        # 2. Customer opt-out check
        if policy.customer_opt_out_enabled and customer and customer.opted_out:
            checks["customer_opt_out"] = {"passed": False, "details": "Customer has opted out of automated communications"}
            return False, "BLOCKED: Customer opted out of automatic recovery", checks

        # 3. Recovery window check
        if case.created_at:
            created_at = case.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            window_end = created_at + timedelta(hours=policy.recovery_window_hours)
            if now > window_end:
                checks["recovery_window"] = {"passed": False, "details": f"Case expired after {policy.recovery_window_hours} hours"}
                return False, f"BLOCKED: Recovery window of {policy.recovery_window_hours} hours has elapsed", checks

        # 4. Retry limit check (for RETRY action)
        if action_type == "RETRY":
            if case.retry_count >= policy.max_retries:
                checks["retry_limit"] = {"passed": False, "details": f"Maximum retry limit ({policy.max_retries}) reached"}
                return False, f"BLOCKED: Maximum retry count ({policy.max_retries}) reached", checks
                
            if case.revenue_at_risk > policy.max_auto_retry_amount:
                checks["max_auto_retry_amount"] = {"passed": False, "details": f"Amount ${case.revenue_at_risk:,.2f} exceeds auto-retry limit (${policy.max_auto_retry_amount:,.2f})"}
                return False, f"BLOCKED: Amount exceeds maximum automatic retry limit of ${policy.max_auto_retry_amount:,.2f}", checks

        # 5. Duplicate action check
        if policy.duplicate_action_protection:
            recent_same_action = db.query(RecoveryAction).filter(
                RecoveryAction.case_id == case.id,
                RecoveryAction.action_type == action_type,
                RecoveryAction.status == "FAILED"
            ).count()
            if recent_same_action >= 2:
                checks["duplicate_action"] = {"passed": False, "details": f"Action '{action_type}' already failed {recent_same_action} times"}
                return False, f"BLOCKED: Action '{action_type}' repeatedly failed without state change", checks

        return True, "ALLOWED: Action complies with all active operational policies", checks

policy_engine = PolicyEngine()
