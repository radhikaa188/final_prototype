import os
import random
import joblib
import numpy as np
import pandas as pd

SAVED_MODELS_DIR = os.path.join(os.path.dirname(__file__), "saved_models")
MODEL_PATH = os.path.join(SAVED_MODELS_DIR, "recovery_model.joblib")
PREPROC_PATH = os.path.join(SAVED_MODELS_DIR, "recovery_preprocessor.joblib")

class MLPredictor:
    def __init__(self):
        self.recovery_model = None
        self.recovery_preprocessor = None
        self.is_trained = False
        self.load_saved_artifacts()

    def load_saved_artifacts(self):
        """Loads persisted Joblib ML model and preprocessor from disk"""
        if os.path.exists(MODEL_PATH) and os.path.exists(PREPROC_PATH):
            try:
                self.recovery_model = joblib.load(MODEL_PATH)
                self.recovery_preprocessor = joblib.load(PREPROC_PATH)
                self.is_trained = True
                print(f"[MLPredictor] Loaded persisted Recovery ML Model and Preprocessor from {SAVED_MODELS_DIR}")
            except Exception as e:
                print(f"[MLPredictor] Error loading model artifacts: {e}")
                self.is_trained = False
        else:
            print("[MLPredictor] WARNING: Recovery ML model artifact is unavailable. Run 'python backend/app/ml/train_models.py' to generate artifacts.")
            self.is_trained = False

    def predict_root_cause_rules(self, payment_amount: float, failure_reason: str, failure_category: str = "", attempt_number: int = 1, customer_tenure: int = 12, ticket_count: int = 0) -> tuple[str, float]:
        """
        Rule-Based Diagnosis (Root Cause Rules Engine)
        Classifies decline symptoms using operational heuristics.
        Note: This is a Rule-Based Diagnosis component, not a trained ML classifier.
        """
        reason_upper = str(failure_reason or failure_category).upper()

        if "NETWORK" in reason_upper or "TIMEOUT" in reason_upper or "SYSTEM" in reason_upper or "GATEWAY" in reason_upper or "BANK_UNAVAILABLE" in reason_upper or attempt_number == 1:
            cause = "TRANSIENT_FAILURE"
            confidence = 0.88
        elif "EXPIRED" in reason_upper or "CARD" in reason_upper or "INSUFFICIENT" in reason_upper or "DECLINED" in reason_upper or "LIMIT" in reason_upper:
            cause = "CUSTOMER_ACTION"
            confidence = 0.92
        elif "FRAUD" in reason_upper or "RISK" in reason_upper or "SUSPICIOUS" in reason_upper or ticket_count > 3:
            cause = "RISK_RELATED"
            confidence = 0.95
        else:
            hash_val = int(payment_amount * 100 + customer_tenure + attempt_number) % 4
            causes = ["TRANSIENT_FAILURE", "CUSTOMER_ACTION", "RISK_RELATED", "OTHER"]
            cause = causes[hash_val]
            confidence = 0.78

        return cause, confidence

    # Alias for backward compatibility
    predict_root_cause = predict_root_cause_rules

    def predict_recovery_probability(
        self,
        payment_amount: float,
        failure_category: str = "TRANSIENT_TIMEOUT",
        customer_ltv: float = 500.0,
        customer_tenure: int = 12,
        attempt_number: int = 1,
        previous_failures: int = 0,
        days_since_last_payment: int = 30,
        historical_success_rate: float = 0.85,
        monthly_charge: float = 50.0,
        payment_method: str = "Credit Card",
        gateway_response_code: str = "2000",
        ticket_count: int = 0
    ) -> float:
        """
        Model 2 — Recovery Probability P(Recovery) in [0.0, 1.0]
        Inference executed directly via loaded joblib model trained on payment_failure telemetry.
        """
        if not (self.is_trained and self.recovery_model is not None and self.recovery_preprocessor is not None):
            raise RuntimeError("Recovery ML model artifact is unavailable. Run 'python backend/app/ml/train_models.py' to generate artifacts.")

        # Normalize failure_reason category string
        reason = str(failure_category).upper()
        if "TIMEOUT" in reason or "TRANSIENT" in reason:
            fail_reason = "TRANSIENT_TIMEOUT"
        elif "GATEWAY" in reason or "SYSTEM" in reason:
            fail_reason = "GATEWAY_ERROR"
        elif "INSUFFICIENT" in reason:
            fail_reason = "INSUFFICIENT_FUNDS"
        elif "EXPIRED" in reason:
            fail_reason = "CARD_EXPIRED"
        elif "FRAUD" in reason or "RISK" in reason:
            fail_reason = "FRAUD_RISK"
        elif "CLOSED" in reason:
            fail_reason = "ACCOUNT_CLOSED"
        else:
            fail_reason = "CARD_DECLINED"

        # Build feature DataFrame matching exact telemetry feature space
        feature_dict = {
            'amount_usd': float(payment_amount),
            'attempt_number': int(attempt_number),
            'previous_failures': int(previous_failures),
            'days_since_last_payment': int(days_since_last_payment),
            'historical_success_rate': float(historical_success_rate),
            'customer_tenure_months': int(customer_tenure),
            'monthly_charge_usd': float(monthly_charge),
            'support_ticket_count': int(ticket_count),
            'failure_reason': fail_reason,
            'gateway_response_code': str(gateway_response_code),
            'payment_method': str(payment_method),
            'day_of_week': '1' # Tuesday default
        }

        X_sample = pd.DataFrame([feature_dict])
        X_proc = self.recovery_preprocessor.transform(X_sample)
        
        # Predict probability of class 1 (Recovered)
        proba = self.recovery_model.predict_proba(X_proc)[0][1]
        
        return round(float(np.clip(proba, 0.05, 0.98)), 4)

predictor = MLPredictor()
