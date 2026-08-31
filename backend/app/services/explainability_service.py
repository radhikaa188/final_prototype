from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

class DecisionExplainabilityService:
    """
    Generates structured, domain-informed decision explanations for RecoverAI recovery recommendations.
    Separates Recovery Probability P(Recovery) from Action Model Confidence.
    """

    def explain_decision(
        self,
        case: Any,
        payment: Any,
        customer: Any,
        probabilities: Optional[Dict[str, float]] = None,
        guardrail_result: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        action = case.recommended_action or "RETRY"
        rec_prob = float(case.recovery_probability or 0.5)
        conf = float(case.agent_confidence or 0.85)
        factors: List[Dict[str, Any]] = []

        # 1. Root Cause Factor
        cause = case.root_cause or (payment.failure_category if payment else "TRANSIENT_FAILURE")
        if cause in ("TRANSIENT_FAILURE", "GATEWAY_TIMEOUT", "BAD_REQUEST_ERROR"):
            factors.append({
                "feature": "root_cause",
                "value": cause,
                "impact": "positive",
                "importance": "high",
                "explanation": f"Decline was diagnosed as {cause}. Transient network/gateway declines respond well to automated retries."
            })
        elif cause in ("INSUFFICIENT_FUNDS", "CUSTOMER_ACTION"):
            factors.append({
                "feature": "root_cause",
                "value": cause,
                "impact": "negative",
                "importance": "high",
                "explanation": "Customer action is required to resolve balance or card issues before execution."
            })
        else:
            factors.append({
                "feature": "root_cause",
                "value": cause,
                "impact": "neutral",
                "importance": "medium",
                "explanation": f"Decline diagnosed as {cause}."
            })

        # 2. Recovery Probability Factor
        if rec_prob >= 0.70:
            factors.append({
                "feature": "recovery_probability",
                "value": f"{rec_prob*100:.0f}%",
                "impact": "positive",
                "importance": "high",
                "explanation": f"ML model estimates high recovery likelihood of {rec_prob*100:.0f}% based on historical transaction features."
            })
        elif rec_prob < 0.40:
            factors.append({
                "feature": "recovery_probability",
                "value": f"{rec_prob*100:.0f}%",
                "impact": "negative",
                "importance": "high",
                "explanation": f"ML model estimates lower recovery likelihood ({rec_prob*100:.0f}%)."
            })
        else:
            factors.append({
                "feature": "recovery_probability",
                "value": f"{rec_prob*100:.0f}%",
                "impact": "neutral",
                "importance": "medium",
                "explanation": f"Moderate recovery likelihood of {rec_prob*100:.0f}%."
            })

        # 3. Retry Count / Velocity Factor
        retry_count = int(case.retry_count or 0)
        if retry_count == 0:
            factors.append({
                "feature": "retry_count",
                "value": "0 previous retries",
                "impact": "positive",
                "importance": "medium",
                "explanation": "First recovery attempt allows standard immediate recovery strategy."
            })
        elif retry_count >= 2:
            factors.append({
                "feature": "retry_count",
                "value": f"{retry_count} retries",
                "impact": "negative",
                "importance": "high",
                "explanation": f"Case has undergone {retry_count} previous attempts; risk of customer fatigue increases."
            })
        else:
            factors.append({
                "feature": "retry_count",
                "value": f"{retry_count} retry",
                "impact": "neutral",
                "importance": "low",
                "explanation": f"Case has {retry_count} recorded prior attempt."
            })

        # 4. Customer Opt-Out Status
        if customer and customer.opted_out:
            factors.append({
                "feature": "customer_opted_out",
                "value": "True",
                "impact": "negative",
                "importance": "high",
                "explanation": "Customer has opted out of automated communications/retries."
            })

        # 5. Customer Value & Tenure
        if customer:
            ltv = float(customer.lifetime_value or 0.0)
            if ltv >= 500.0:
                factors.append({
                    "feature": "customer_ltv",
                    "value": f"${ltv:,.2f}",
                    "impact": "positive",
                    "importance": "medium",
                    "explanation": f"High Customer Lifetime Value (${ltv:,.2f}) prioritizes proactive retention."
                })

        # 6. Policy Guardrails Validation
        if guardrail_result:
            allowed = guardrail_result.get("allowed", True)
            reason = guardrail_result.get("reason", "Passed all policy checks")
            factors.append({
                "feature": "guardrail_policy",
                "value": "ALLOWED" if allowed else "BLOCKED",
                "impact": "positive" if allowed else "negative",
                "importance": "high",
                "explanation": f"Policy Engine check: {reason}"
            })

        return {
            "recommended_action": action,
            "recovery_probability": rec_prob,
            "action_confidence": conf,
            "factors": factors
        }

explainability_service = DecisionExplainabilityService()
