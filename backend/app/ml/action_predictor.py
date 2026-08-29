import os
import joblib
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional

SAVED_MODELS_DIR = os.path.join(os.path.dirname(__file__), "saved_models")
ACTION_MODEL_PATH = os.path.join(SAVED_MODELS_DIR, "action_model.joblib")
ACTION_PREPROC_PATH = os.path.join(SAVED_MODELS_DIR, "action_preprocessor.joblib")

class ActionPredictor:
    def __init__(self):
        self.action_model = None
        self.action_preprocessor = None
        self.is_trained = False
        self.load_saved_artifacts()

    def load_saved_artifacts(self):
        """Loads persisted Action Selection ML Model and Preprocessor from disk"""
        if os.path.exists(ACTION_MODEL_PATH) and os.path.exists(ACTION_PREPROC_PATH):
            try:
                self.action_model = joblib.load(ACTION_MODEL_PATH)
                self.action_preprocessor = joblib.load(ACTION_PREPROC_PATH)
                self.is_trained = True
                print(f"[ActionPredictor] Loaded persisted Action Selection ML Model and Preprocessor from {SAVED_MODELS_DIR}")
            except Exception as e:
                print(f"[ActionPredictor] Error loading action model artifacts: {e}")
                self.is_trained = False
        else:
            print("[ActionPredictor] WARNING: Action ML model artifacts unavailable. Run 'python backend/app/ml/train_action_model.py'.")
            self.is_trained = False

    def predict_action(
        self,
        amount_usd: float,
        failure_reason: str = "CARD_DECLINED",
        gateway_response_code: str = "2000",
        attempt_number: int = 1,
        previous_failures: int = 0,
        days_since_last_payment: int = 30,
        historical_success_rate: float = 0.85,
        payment_method: str = "card",
        customer_tenure_months: int = 12,
        monthly_charge_usd: float = 50.0,
        support_ticket_count: int = 0,
        customer_lifetime_value_usd: float = 500.0,
        customer_opted_out: bool = False,
        recovery_probability: float = 0.50,
        root_cause: str = "TRANSIENT_FAILURE",
        root_cause_confidence: float = 0.85,
        revenue_at_risk: float = 50.0,
        expected_recovery: float = 25.0
    ) -> Dict[str, Any]:
        """
        Inference executed directly via loaded joblib Action Selection model.
        Returns predicted action, confidence score, and full 4-class probability distribution.
        """
        if not (self.is_trained and self.action_model is not None and self.action_preprocessor is not None):
            raise RuntimeError("Action ML model artifact is unavailable. Run 'python backend/app/ml/train_action_model.py'.")

        feature_dict = {
            'amount_usd': float(amount_usd),
            'attempt_number': int(attempt_number),
            'previous_failures': int(previous_failures),
            'days_since_last_payment': int(days_since_last_payment),
            'historical_success_rate': float(historical_success_rate),
            'customer_tenure_months': int(customer_tenure_months),
            'monthly_charge_usd': float(monthly_charge_usd),
            'support_ticket_count': int(support_ticket_count),
            'customer_lifetime_value_usd': float(customer_lifetime_value_usd),
            'recovery_probability': float(recovery_probability),
            'root_cause_confidence': float(root_cause_confidence),
            'revenue_at_risk': float(revenue_at_risk),
            'expected_recovery': float(expected_recovery),
            'failure_reason': str(failure_reason),
            'gateway_response_code': str(gateway_response_code),
            'payment_method': str(payment_method),
            'root_cause': str(root_cause),
            'customer_opted_out': int(customer_opted_out)
        }

        X_sample = pd.DataFrame([feature_dict])
        X_proc = self.action_preprocessor.transform(X_sample)

        probas = self.action_model.predict_proba(X_proc)[0]
        classes = self.action_model.classes_

        prob_dict = {str(cls): round(float(p), 4) for cls, p in zip(classes, probas)}
        
        best_idx = int(np.argmax(probas))
        predicted_action = str(classes[best_idx])
        confidence = round(float(probas[best_idx]), 4)

        return {
            "predicted_action": predicted_action,
            "confidence": confidence,
            "probabilities": prob_dict,
            "model": type(self.action_model).__name__,
            "ml_used": True
        }

action_predictor = ActionPredictor()
