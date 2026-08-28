import json
import logging
import urllib.request
import urllib.error
from typing import Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session
from app.config import settings
from app.db.models import RecoveryCase, Payment, Customer
from app.policies.guardrails import PolicyEngine

logger = logging.getLogger("recoverai.recovery_agent")

SYSTEM_PROMPT = """You are the RecoverAI Autonomous Revenue Recovery Decision Agent.
Your role is to analyze failed payment case context, customer profile telemetry, quantitative ML model predictions, root cause diagnosis, and operational guardrail policies to recommend the optimal recovery intervention.

You MUST recommend EXACTLY ONE of the following 4 allowed actions:
1. RETRY: Schedule an automated payment retry through payment gateway.
2. CUSTOMER_NUDGE: Send an automated email/in-app notification requesting the customer update their billing details.
3. HUMAN_REVIEW: Escalate case to human operations team for manual review and tailored outreach.
4. STOP: Halt all automated recovery interventions to avoid customer friction or unrecoverable costs.

CRITICAL INSTRUCTIONS:
- Base your recommendation on financial risk, P(Recovery) score, decline root cause, and retry history.
- Never invent customer/payment facts.
- Never claim a payment succeeded or an email was dispatched.
- Your recommendation is advisory and will be validated against deterministic policy guardrails.
- Respond STRICTLY in valid JSON matching this schema:
{
  "recommended_action": "RETRY" | "CUSTOMER_NUDGE" | "HUMAN_REVIEW" | "STOP",
  "reason": "<detailed rationale explaining why this action is optimal>",
  "confidence": <float between 0.50 and 0.99>,
  "risk_assessment": "LOW" | "MEDIUM" | "HIGH",
  "supporting_factors": ["<factor 1>", "<factor 2>", "<factor 3>"]
}
"""

class RecoveryAgent:
    def __init__(self, version: str = "v2.0.0-llm"):
        self.version = version

    def evaluate_case(self, db: Session, case: RecoveryCase) -> Tuple[str, str, float]:
        """
        Evaluates recovery case using Mistral LLM API for advisory decision making.
        Returns: (recommended_action, reasoning, confidence)
        """
        res = self.evaluate_case_full(db, case)
        return res["recommended_action"], res["reason"], res["confidence"]

    def evaluate_case_full(self, db: Session, case: RecoveryCase) -> Dict[str, Any]:
        """
        Full evaluation method returning structured metadata (llm_used, model, action, reason, confidence, supporting_factors).
        """
        payment = db.query(Payment).filter(Payment.id == case.payment_id).first()
        customer = db.query(Customer).filter(Customer.id == case.customer_id).first()
        policy = PolicyEngine.get_active_policy(db)

        context = {
            "payment": {
                "id": payment.id if payment else "unknown",
                "gateway_payment_id": payment.gateway_payment_id if payment else "unknown",
                "amount": payment.amount if payment else case.revenue_at_risk,
                "currency": payment.currency if payment else "USD",
                "status": payment.status if payment else "FAILED",
                "failure_reason": payment.failure_reason if payment else "unknown",
                "failure_category": payment.failure_category if payment else "unknown",
                "attempt_number": payment.attempt_number if payment else 1
            },
            "customer": {
                "id": customer.id if customer else "unknown",
                "external_customer_id": customer.external_customer_id if customer else "unknown",
                "name": customer.name if customer else "unknown",
                "lifetime_value": customer.lifetime_value if customer else 0.0,
                "opted_out": customer.opted_out if customer else False
            },
            "recovery_intelligence": {
                "root_cause": case.root_cause or "TRANSIENT_FAILURE",
                "root_cause_confidence": case.root_cause_confidence or 0.85,
                "recovery_probability": case.recovery_probability or 0.50,
                "expected_recovery": case.expected_recovery or 0.0,
                "revenue_at_risk": case.revenue_at_risk,
                "priority_score": case.priority_score or 0.0,
                "retry_count": case.retry_count
            },
            "operational_policies": {
                "max_retries": policy.max_retries,
                "max_auto_retry_amount": policy.max_auto_retry_amount,
                "recovery_window_hours": policy.recovery_window_hours,
                "customer_opt_out_enabled": policy.customer_opt_out_enabled
            }
        }

        api_key = settings.MISTRAL_API_KEY
        if api_key:
            try:
                llm_res = self._call_mistral_llm(context, api_key)
                if llm_res and "recommended_action" in llm_res:
                    action = self._normalize_action(llm_res["recommended_action"])
                    reason = llm_res.get("reason", "LLM decision based on case telemetry.")
                    confidence = float(llm_res.get("confidence", 0.85))
                    confidence = round(min(max(confidence, 0.5), 0.99), 2)
                    
                    logger.info(f"[RecoveryAgent LLM] Action: {action} | Conf: {confidence} | Reason: {reason}")
                    return {
                        "llm_used": True,
                        "model": settings.MISTRAL_MODEL,
                        "recommended_action": action,
                        "reason": reason,
                        "confidence": confidence,
                        "risk_assessment": llm_res.get("risk_assessment", "MEDIUM"),
                        "supporting_factors": llm_res.get("supporting_factors", [])
                    }
            except Exception as e:
                logger.warning(f"[RecoveryAgent] LLM API call failed ({e}). Falling back to rule-based engine.")

        # Fallback to rule-based engine if LLM unconfigured or failed
        action, reason, conf = self._evaluate_case_rule_fallback(case, payment, customer, policy)
        return {
            "llm_used": False,
            "model": "rule_based_fallback",
            "recommended_action": action,
            "reason": reason,
            "confidence": conf,
            "risk_assessment": "MEDIUM",
            "supporting_factors": ["Rule-based fallback engine executed"]
        }

    def _call_mistral_llm(self, context: Dict[str, Any], api_key: str) -> Optional[Dict[str, Any]]:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        user_prompt = f"Evaluate the following revenue recovery case and return structured JSON decision:\n{json.dumps(context, indent=2)}"
        
        payload = {
            "model": settings.MISTRAL_MODEL,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.2
        }

        req = urllib.request.Request(
            "https://api.mistral.ai/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers
        )

        with urllib.request.urlopen(req, timeout=10) as response:
            res_body = json.loads(response.read().decode("utf-8"))
            content = res_body["choices"][0]["message"]["content"]
            return json.loads(content)

    def _normalize_action(self, raw_action: str) -> str:
        act_str = str(raw_action).strip().upper()
        if "RETRY" in act_str:
            return "RETRY"
        elif "NUDGE" in act_str or "EMAIL" in act_str or "NOTIF" in act_str:
            return "CUSTOMER_NUDGE"
        elif "HUMAN" in act_str or "REVIEW" in act_str or "ESCALAT" in act_str or "MANUAL" in act_str:
            return "HUMAN_REVIEW"
        elif "STOP" in act_str or "HALT" in act_str or "CANCEL" in act_str:
            return "STOP"
        return "RETRY"

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
