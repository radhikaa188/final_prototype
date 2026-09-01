from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.db.session import get_db
from app.db.models import Payment, Customer, RecoveryCase, User
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
def global_search(
    q: str = Query("", description="Search query across payments, customers, and cases"),
    limit: int = Query(10, description="Max results per entity type"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    query_str = (q or "").strip()
    if not query_str:
        return {
            "query": "",
            "total_results": 0,
            "payments": [],
            "customers": [],
            "recovery_cases": []
        }

    pattern = f"%{query_str}%"

    # 1. Search Payments
    payments_raw = (
        db.query(Payment)
        .filter(
            or_(
                Payment.id.ilike(pattern),
                Payment.gateway_payment_id.ilike(pattern),
                Payment.failure_reason.ilike(pattern),
                Payment.failure_category.ilike(pattern),
                Payment.status.ilike(pattern)
            )
        )
        .order_by(Payment.created_at.desc())
        .limit(limit)
        .all()
    )

    payments = []
    for p in payments_raw:
        cust = db.query(Customer).filter(Customer.id == p.customer_id).first() if p.customer_id else None
        case = db.query(RecoveryCase).filter(RecoveryCase.payment_id == p.id).first()
        payments.append({
            "id": p.id,
            "gateway_payment_id": p.gateway_payment_id,
            "customer_id": p.customer_id,
            "customer_name": cust.name if cust else "Unknown Customer",
            "amount": p.amount,
            "currency": p.currency,
            "status": p.status,
            "failure_reason": p.failure_reason,
            "failure_category": p.failure_category,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "recovery_case_id": case.id if case else None,
            "recovery_case_status": case.status if case else None
        })

    # 2. Search Customers
    customers_raw = (
        db.query(Customer)
        .filter(
            or_(
                Customer.id.ilike(pattern),
                Customer.external_customer_id.ilike(pattern),
                Customer.name.ilike(pattern),
                Customer.email.ilike(pattern),
                Customer.phone.ilike(pattern)
            )
        )
        .limit(limit)
        .all()
    )

    customers = []
    for c in customers_raw:
        case_count = db.query(RecoveryCase).filter(RecoveryCase.customer_id == c.id).count()
        customers.append({
            "id": c.id,
            "external_customer_id": c.external_customer_id,
            "name": c.name,
            "email": c.email,
            "phone": c.phone,
            "lifetime_value": c.lifetime_value,
            "opted_out": c.opted_out,
            "active_cases_count": case_count
        })

    # 3. Search Recovery Cases
    cases_raw = (
        db.query(RecoveryCase)
        .filter(
            or_(
                RecoveryCase.id.ilike(pattern),
                RecoveryCase.payment_id.ilike(pattern),
                RecoveryCase.customer_id.ilike(pattern),
                RecoveryCase.status.ilike(pattern),
                RecoveryCase.root_cause.ilike(pattern),
                RecoveryCase.recommended_action.ilike(pattern),
                RecoveryCase.next_action.ilike(pattern),
                RecoveryCase.customer_action_type.ilike(pattern)
            )
        )
        .order_by(RecoveryCase.priority_score.desc())
        .limit(limit)
        .all()
    )

    cases = []
    for case in cases_raw:
        cust = db.query(Customer).filter(Customer.id == case.customer_id).first() if case.customer_id else None
        pay = db.query(Payment).filter(Payment.id == case.payment_id).first() if case.payment_id else None
        cases.append({
            "id": case.id,
            "payment_id": case.payment_id,
            "gateway_payment_id": pay.gateway_payment_id if pay else None,
            "customer_id": case.customer_id,
            "customer_name": cust.name if cust else "Unknown Customer",
            "revenue_at_risk": case.revenue_at_risk,
            "expected_recovery": case.expected_recovery,
            "status": case.status,
            "root_cause": case.root_cause,
            "recommended_action": case.recommended_action,
            "next_action": case.next_action,
            "priority_score": case.priority_score
        })

    total = len(payments) + len(customers) + len(cases)
    return {
        "query": query_str,
        "total_results": total,
        "payments": payments,
        "customers": customers,
        "recovery_cases": cases
    }
