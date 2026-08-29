import json
import logging
import urllib.request
import urllib.error
from typing import Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session
from app.config import settings
from app.db.models import RecoveryCase, Payment, Customer
from app.policies.guardrails import PolicyEngine
from app.ml.action_predictor import action_predictor

logger = logging.getLogger("recoverai.recovery_agent")

class RecoveryAgent:
    def __init__(self, version: str = "v3.0.0-ml"):
        self.version = version

    def evaluate_case(self, db: Session, case: RecoveryCase) -> Tuple[str, str, float]:
        """
        Evaluates recovery case using Supervised ML Action Predictor.
        Returns: (recommended_action, reasoning, confidence)
        """
        res = self.evaluate_case_full(db, case)
        return res["recommended_action"], res["reason"], res["confidence"]

    def evaluate_case_full(self, db: Session, case: RecoveryCase) -> Dict[str, Any]:
        """
        Full evaluation method returning ML Action Selection metadata
        (ml_used, model, action, reason, confidence, probabilities, risk_assessment).
        """
        payment = db.query(Payment).filter(Payment.id == case.payment_id).first()
        customer = db.query(Customer).filter(Customer.id == case.customer_id).first()
        policy = PolicyEngine.get_active_policy(db)

        # 1. Primary Action Selector: Supervised ML Action Predictor
        if action_predictor.is_trained:
            try:
                ml_res = action_predictor.predict_action(
                    amount_usd=payment.amount if payment else case.revenue_at_risk,
                    failure_reason=payment.failure_reason if payment else "CARD_DECLINED",
                    gateway_response_code=getattr(payment, 'gateway_response_code', '2000') if payment else "2000",
                    attempt_number=payment.attempt_number if payment else (case.retry_count + 1),
                    previous_failures=case.retry_count,
                    days_since_last_payment=30,
                    historical_success_rate=0.85,
                    payment_method=getattr(payment, 'payment_method', 'card') if payment else "card",
                    customer_tenure_months=12,
                    monthly_charge_usd=payment.amount if payment else case.revenue_at_risk,
                    support_ticket_count=0,
                    customer_lifetime_value_usd=customer.lifetime_value if customer else 500.0,
                    customer_opted_out=customer.opted_out if customer else False,
                    recovery_probability=case.recovery_probability or 0.50,
                    root_cause=case.root_cause or "TRANSIENT_FAILURE",
                    root_cause_confidence=case.root_cause_confidence or 0.85,
                    revenue_at_risk=case.revenue_at_risk,
                    expected_recovery=case.expected_recovery or 0.0
                )

                action = ml_res["predicted_action"]
                confidence = ml_res["confidence"]
                probs = ml_res["probabilities"]
                model_name = ml_res["model"]

                prob_summary = ", ".join([f"{k}: {v*100:.1f}%" for k, v in probs.items()])
                reason = f"Supervised ML Model ({model_name}) selected {action} with {confidence*100:.1f}% confidence ({prob_summary})."

                logger.info(f"[RecoveryAgent ML] Model: {model_name} | Action: {action} | Conf: {confidence:.4f}")

                return {
                    "ml_used": True,
                    "model": model_name,
                    "recommended_action": action,
                    "reason": reason,
                    "confidence": confidence,
                    "probabilities": probs,
                    "risk_assessment": "LOW" if confidence > 0.80 else ("MEDIUM" if confidence > 0.60 else "HIGH"),
                    "supporting_factors": [
                        f"Supervised ML classifier: {model_name}",
                        f"Model confidence: {confidence*100:.1f}%",
                        f"Root cause signal: {case.root_cause or 'TRANSIENT_FAILURE'}",
                        f"P(Recovery) ML signal: {(case.recovery_probability or 0.5)*100:.1f}%"
                    ]
                }
            except Exception as e:
                logger.warning(f"[RecoveryAgent] ML Action Predictor failed ({e}). Falling back to rule engine.")

        # 2. Fallback to rule-based engine if ML predictor is unconfigured or fails
        action, reason, conf = self._evaluate_case_rule_fallback(case, payment, customer, policy)
        return {
            "ml_used": False,
            "model": "rule_based_fallback",
            "recommended_action": action,
            "reason": reason,
            "confidence": conf,
            "probabilities": {action: conf},
            "risk_assessment": "MEDIUM",
            "supporting_factors": ["Rule-based fallback engine executed"]
        }

    def generate_llm_advisory(self, db: Session, case: RecoveryCase) -> Optional[Dict[str, Any]]:
        """
        Optional Mistral LLM Advisory Provider for detailed natural language explanations.
        Does NOT override the primary Supervised ML Action Model recommendation.
        """
        api_key = settings.MISTRAL_API_KEY
        if not api_key:
            return None

        payment = db.query(Payment).filter(Payment.id == case.payment_id).first()
        customer = db.query(Customer).filter(Customer.id == case.customer_id).first()

        context = {
            "amount": payment.amount if payment else case.revenue_at_risk,
            "root_cause": case.root_cause,
            "recovery_probability": case.recovery_probability,
            "ml_recommended_action": case.recommended_action
        }

        try:
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {
                "model": settings.MISTRAL_MODEL,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": "Analyze case context and return JSON advisory explanation."},
                    {"role": "user", "content": json.dumps(context)}
                ]
            }
            req = urllib.request.Request("https://api.mistral.ai/v1/chat/completions", data=json.dumps(payload).encode('utf-8'), headers=headers)
            with urllib.request.urlopen(req, timeout=5) as res:
                return json.loads(json.loads(res.read().decode('utf-8'))["choices"][0]["message"]["content"])
        except Exception as e:
            logger.warning(f"LLM advisory generation failed: {e}")
            return None

    def _evaluate_case_rule_fallback(self, case: RecoveryCase, payment: Optional[Payment], customer: Optional[Customer], policy: Any) -> Tuple[str, str, float]:
        if customer and customer.opted_out:
            return "STOP", "Customer has opted out of automated communications.", 0.99

        if case.retry_count >= policy.max_retries:
            if case.revenue_at_risk > 1000.0:
                return "HUMAN_REVIEW", f"Automated retries ({case.retry_count}) exhausted on high-value case (${case.revenue_at_risk:,.2f}). Escalating for manual review.", 0.92
            else:
                return "STOP", f"Automated retry limit ({policy.max_retries}) reached without resolution.", 0.95

        if case.revenue_at_risk > policy.max_auto_retry_amount:
            return "HUMAN_REVIEW", f"Transaction amount (${case.revenue_at_risk:,.2f}) exceeds maximum auto-retry threshold (${policy.max_auto_retry_amount:,.2f}). Requires approval.", 0.94

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
        else:
            if prob >= 0.75 and case.retry_count < 2:
                return "RETRY", f"Unclassified failure with high recovery probability ({prob*100:.0f}%). Recommending retry attempt.", 0.76
            elif prob < 0.30:
                return "STOP", f"Low recovery probability ({prob*100:.0f}%). Stopping automated interventions to avoid customer friction.", 0.85
            else:
                return "CUSTOMER_NUDGE", f"Proposing customer notification for payment method verification (P(Recovery)={prob*100:.0f}%).", 0.74

recovery_agent = RecoveryAgent()
