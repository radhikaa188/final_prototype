import random
import time
from typing import Dict, Any

class SimulatedPaymentGateway:
    def __init__(self, force_success_rate: float = 0.75):
        self.force_success_rate = force_success_rate

    def process_retry(
        self, 
        gateway_payment_id: str, 
        amount: float, 
        attempt_number: int,
        original_failure_reason: str = None
    ) -> Dict[str, Any]:
        """
        Simulates payment gateway response (Stripe / Razorpay / Adyen style)
        """
        time.sleep(0.3) # Simulate network latency
        
        # Determine success probability
        # Higher attempt numbers slightly lower success rate unless force test mode or test ID
        base_success = self.force_success_rate
        if "pay_test" in gateway_payment_id or random.random() < base_success:
            return {
                "status": "SUCCESS",
                "transaction_id": f"txn_{random.randint(10000000, 99999999)}",
                "amount_recovered": amount,
                "gateway_code": "200_OK",
                "message": "Payment captured successfully."
            }
        else:
            reason = original_failure_reason or "GATEWAY_TIMEOUT"
            return {
                "status": "FAILED",
                "transaction_id": f"txn_{random.randint(10000000, 99999999)}",
                "amount_recovered": 0.0,
                "gateway_code": "DECLINED",
                "message": f"Payment retry failed: {reason}"
            }


    def process_nudge(self, customer_email: str, amount: float) -> Dict[str, Any]:
        """Dispatches customer payment link reminder notification"""
        time.sleep(0.2)
        return {
            "status": "CUSTOMER_ACTION_REQUIRED",
            "transaction_id": f"txn_nudge_{random.randint(10000000, 99999999)}",
            "amount_recovered": 0.0,
            "gateway_code": "NUDGE_SENT",
            "message": "Customer notification dispatched. Awaiting customer action."
        }

gateway_simulator = SimulatedPaymentGateway()
