import os
import sys
import pandas as pd
from datetime import datetime, timezone

# Add backend root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import engine, Base, SessionLocal
from app.db.models import Customer, Payment, RecoveryCase, Policy, AuditEvent
from app.ml.predictor import predictor
from app.agents.recovery_agent import recovery_agent

def import_dataset():
    print("=" * 60)
    print("RecoverAI — Database Seeding & Dataset Import Pipeline")
    print("=" * 60)

    # 1. Create database schema
    print("\n[1/5] Initializing database tables...")
    Base.metadata.create_all(bind=engine)

    data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
    subscribers_path = os.path.join(data_dir, "subscribers.csv")
    billing_path = os.path.join(data_dir, "billing.csv")
    tickets_path = os.path.join(data_dir, "support_tickets.csv")

    if not (os.path.exists(subscribers_path) and os.path.exists(billing_path)):
        print(f"Error: Required CSV files not found in {data_dir}")
        return

    # 2. Read CSVs
    print("\n[2/5] Reading CSV datasets...")
    subscribers_df = pd.read_csv(subscribers_path, nrows=1000)
    billing_df = pd.read_csv(billing_path, nrows=5000)
    tickets_df = pd.read_csv(tickets_path, nrows=1000) if os.path.exists(tickets_path) else pd.DataFrame()

    print(f"  - Subscribers: {len(subscribers_df)} records")
    print(f"  - Billing Records: {len(billing_df)} records")
    print(f"  - Support Tickets: {len(tickets_df)} records")

    # Using persisted ML model loaded on predictor startup
    print("\n[3/5] Using persisted Recovery ML Model artifact...")

    db = SessionLocal()
    try:
        # Clear existing tables for clean seed
        db.query(AuditEvent).delete()
        db.query(RecoveryCase).delete()
        db.query(Payment).delete()
        db.query(Customer).delete()
        db.query(Policy).delete()
        db.commit()

        # Seed default policy
        policy = Policy(
            id="default_policy",
            max_retries=3,
            recovery_window_hours=72,
            max_auto_retry_amount=10000.0,
            customer_opt_out_enabled=True,
            duplicate_action_protection=True
        )
        db.add(policy)

        # 3. Import Customers
        print("\n[4/5] Ingesting customers and billing records...")
        customer_map = {}
        
        # Take a subset if dataset is huge (e.g. max 500 subscribers & 1000 billing records for swift dev experience)
        sub_sample = subscribers_df.head(500)
        
        for idx, row in sub_sample.iterrows():
            sub_id = str(row['subscriber_id'])
            # Generate deterministic customer details from subscriber_id
            name = f"Customer {sub_id}"
            email = f"user.{sub_id.lower()}@example.com"
            phone = f"+1-555-01{idx:02d}"
            
            # Map plan and tenure to LTV calculation
            monthly_charge = float(row.get('monthly_charge_usd', 50.0))
            tenure = int(row.get('tenure_months', 6))
            ltv = round(monthly_charge * (tenure + 12), 2)
            
            cust = Customer(
                external_customer_id=sub_id,
                name=name,
                email=email,
                phone=phone,
                customer_since=datetime.now(timezone.utc),
                lifetime_value=ltv,
                opted_out=bool(idx % 25 == 0) # 4% opted out
            )
            db.add(cust)
            db.flush()
            customer_map[sub_id] = cust

        db.commit()
        print(f"  - Successfully created {len(customer_map)} customer accounts.")

        # 4. Import Payments & Create Recovery Cases for Failed Payments
        billing_sample = billing_df[billing_df['subscriber_id'].isin(customer_map.keys())].head(300)
        
        cases_created = 0
        total_risk = 0.0
        total_expected_rec = 0.0

        failure_reasons_pool = [
            ("INSUFFICIENT_FUNDS", "CUSTOMER_ACTION"),
            ("CARD_EXPIRED", "CUSTOMER_ACTION"),
            ("NETWORK_TIMEOUT", "TRANSIENT_FAILURE"),
            ("BANK_UNAVAILABLE", "TRANSIENT_FAILURE"),
            ("SUSPICIOUS_ACTIVITY", "RISK_RELATED"),
            ("DO_NOT_HONOR", "CUSTOMER_ACTION")
        ]

        for idx, row in billing_sample.iterrows():
            sub_id = str(row['subscriber_id'])
            cust = customer_map.get(sub_id)
            if not cust:
                continue

            pay_status = str(row['payment_status']).strip().lower()
            billed_usd = float(row.get('total_billed_usd', row.get('base_charge_usd', 49.99)))
            
            # Determine if this billing record represents a failed payment
            is_failed = pay_status in ['unpaid', 'failed', 'declined', 'late_fee_usd'] or (billed_usd > 80.0 and idx % 3 == 0) or (idx % 4 == 0)
            
            status_str = "FAILED" if is_failed else "SUCCESS"
            fail_reason, fail_cat = failure_reasons_pool[idx % len(failure_reasons_pool)] if is_failed else (None, None)

            pay_id = f"pay_{sub_id.lower()}_{row.get('year_month', '2026-05')}_{idx}"
            payment = Payment(
                gateway_payment_id=pay_id,
                customer_id=cust.id,
                amount=billed_usd,
                currency="USD",
                status=status_str,
                failure_reason=fail_reason,
                failure_category=fail_cat,
                attempt_number=1 if is_failed else 1
            )
            db.add(payment)
            db.flush()

            if is_failed:
                # ML Predictions
                cause, conf = predictor.predict_root_cause(billed_usd, fail_reason, fail_cat, 1)
                prob = predictor.predict_recovery_probability(billed_usd, fail_cat, cust.lifetime_value, 12, 1)
                exp_rec = round(billed_usd * prob, 2)
                prio_score = exp_rec

                case = RecoveryCase(
                    payment_id=payment.id,
                    customer_id=cust.id,
                    status="OPEN",
                    revenue_at_risk=billed_usd,
                    recovery_probability=prob,
                    expected_recovery=exp_rec,
                    priority_score=prio_score,
                    root_cause=cause,
                    root_cause_confidence=conf,
                    retry_count=0,
                    created_at=datetime.now(timezone.utc)
                )
                
                # Agent recommendation
                rec_action, reason, agent_conf = recovery_agent.evaluate_case(db, case)
                case.recommended_action = rec_action
                case.agent_confidence = agent_conf
                case.next_action = rec_action
                case.status = "PRIORITIZED"

                db.add(case)
                cases_created += 1
                total_risk += billed_usd
                total_expected_rec += exp_rec

        db.commit()

        print("\n[5/5] Seed Pipeline Completed Successfully!")
        print("=" * 60)
        print(f"Total Recovery Cases Created : {cases_created}")
        print(f"Total Revenue At Risk        : ${total_risk:,.2f}")
        print(f"Expected Recoverable Revenue : ${total_expected_rec:,.2f}")
        print("=" * 60)

    except Exception as e:
        db.rollback()
        print(f"Seed pipeline error: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    import_dataset()
