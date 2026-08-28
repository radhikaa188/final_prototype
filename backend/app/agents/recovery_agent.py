from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session
from app.db.models import RecoveryCase, Payment, Customer
from app.policies.guardrails import PolicyEngine

class RecoveryAgent:
    def __init__(self, version: str = "v1.0.0"):
        self.version = version

    def evaluate_case(self, db: Session, case: RecoveryCase) -> Tuple[str, str, float]:
        """
        Evaluates the recovery case and proposes the next optimal recovery action.
        Returns: (recommended_action, reasoning, confidence)
        """
        payment = db.query(Payment).filter(Payment.id == case.payment_id).first()
        customer = db.query(Customer).filter(Customer.id == case.customer_id).first()
        policy = PolicyEngine.get_active_policy(db)

        # 1. Customer Opted Out or Retries Exhausted -> STOP / HUMAN_REVIEW
        if customer and customer.opted_out:
            return "STOP", "Customer has opted out of automated communications.", 0.99

        if case.retry_count >= policy.max_retries:
            if case.revenue_at_risk > 1000.0:
                return "HUMAN_REVIEW", f"Automated retries ({case.retry_count}) exhausted on high-value case (${case.revenue_at_risk:,.2f}). Escalating for manual review.", 0.92
            else:
                return "STOP", f"Automated retry limit ({policy.max_retries}) reached without resolution.", 0.95

        # 2. High-value transaction policy override -> HUMAN_REVIEW
        if case.revenue_at_risk > policy.max_auto_retry_amount:
            return "HUMAN_REVIEW", f"Transaction amount (${case.revenue_at_risk:,.2f}) exceeds maximum auto-retry threshold (${policy.max_auto_retry_amount:,.2f}). Requires approval.", 0.94

        # 3. Root cause & recovery probability based decision
        root_cause = case.root_cause or "TRANSIENT_FAILURE"
        prob = case.recovery_probability or 0.50

        if root_cause == "TRANSIENT_FAILURE":
            if prob >= 0.60:
                return "RETRY", f"Failure appears transient ({root_cause}), P(Recovery) is high ({prob*100:.0f}%), and attempt count ({case.retry_count}) is within limit.", round(0.85 + (prob * 0.1), 2)
            else:
                return "CUSTOMER_NUDGE", f"Failure is transient but P(Recovery) is moderate ({prob*100:.0f}%). Proposing customer payment nudge.", 0.78

        elif root_cause == "CUSTOMER_ACTION":
            if case.retry_count == 0:
                return "CUSTOMER_NUDGE", f"Root cause requires customer action ({payment.failure_reason if payment else 'card update'}). Proposing automated payment retry nudge.", 0.89
            else:
                return "HUMAN_REVIEW", "Customer nudge already attempted. Requesting operational review for tailored outreach.", 0.81

        elif root_cause == "RISK_RELATED":
            return "HUMAN_REVIEW", "Risk-related payment decline detected. Escalating to fraud and compliance team for manual review.", 0.96

        else: # OTHER
            if prob >= 0.75 and case.retry_count < 2:
                return "RETRY", f"Unclassified failure with high recovery probability ({prob*100:.0f}%). Recommending retry attempt.", 0.76
            elif prob < 0.30:
                return "STOP", f"Low recovery probability ({prob*100:.0f}%). Stopping automated interventions to avoid customer friction.", 0.85
            else:
                return "CUSTOMER_NUDGE", f"Proposing customer notification for payment method verification (P(Recovery)={prob*100:.0f}%).", 0.74

recovery_agent = RecoveryAgent()
