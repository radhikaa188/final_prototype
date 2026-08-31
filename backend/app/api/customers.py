from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.session import get_db
from app.db.models import Customer, Payment, RecoveryCase, RecoveryAction, User
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/customers", tags=["customers"])

@router.get("")
def list_customers(
    limit: int = Query(100),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Customer)
    total = query.count()
    customers = query.offset(offset).limit(limit).all()

    res = []
    for c in customers:
        total_payments = db.query(Payment).filter(Payment.customer_id == c.id).count()
        successful_payments = db.query(Payment).filter(Payment.customer_id == c.id, Payment.status == "SUCCESS").count()
        failed_payments = db.query(Payment).filter(Payment.customer_id == c.id, Payment.status == "FAILED").count()
        
        # Recovered revenue for this customer
        recovered_rev = db.query(func.sum(RecoveryAction.amount_recovered)).join(RecoveryCase).filter(
            RecoveryCase.customer_id == c.id, RecoveryAction.status == "SUCCESS"
        ).scalar() or 0.0

        outstanding_rev = db.query(func.sum(RecoveryCase.revenue_at_risk)).filter(
            RecoveryCase.customer_id == c.id, RecoveryCase.status != "RECOVERED"
        ).scalar() or 0.0

        res.append({
            "id": c.id,
            "external_customer_id": c.external_customer_id,
            "name": c.name,
            "email": c.email,
            "phone": c.phone,
            "lifetime_value": c.lifetime_value,
            "opted_out": c.opted_out,
            "total_payments": total_payments,
            "successful_payments": successful_payments,
            "failed_payments": failed_payments,
            "recovered_revenue": round(recovered_rev, 2),
            "outstanding_revenue": round(outstanding_rev, 2),
            "customer_since": c.customer_since.isoformat() if c.customer_since else None
        })

    return {"total": total, "customers": res}

@router.get("/{customer_id}")
def get_customer_detail(customer_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    c = db.query(Customer).filter(Customer.id == customer_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")

    payments = db.query(Payment).filter(Payment.customer_id == c.id).order_by(Payment.created_at.desc()).all()
    cases = db.query(RecoveryCase).filter(RecoveryCase.customer_id == c.id).order_by(RecoveryCase.created_at.desc()).all()

    payment_history = []
    for p in payments:
        payment_history.append({
            "id": p.id,
            "gateway_payment_id": p.gateway_payment_id,
            "amount": p.amount,
            "status": p.status,
            "failure_reason": p.failure_reason,
            "created_at": p.created_at.isoformat() if p.created_at else None
        })

    recovery_history = []
    for case in cases:
        actions = db.query(RecoveryAction).filter(RecoveryAction.case_id == case.id).all()
        recovery_history.append({
            "id": case.id,
            "revenue_at_risk": case.revenue_at_risk,
            "status": case.status,
            "root_cause": case.root_cause,
            "recovery_probability": case.recovery_probability,
            "recommended_action": case.recommended_action,
            "actions_count": len(actions),
            "created_at": case.created_at.isoformat() if case.created_at else None
        })

    return {
        "id": c.id,
        "external_customer_id": c.external_customer_id,
        "name": c.name,
        "email": c.email,
        "phone": c.phone,
        "lifetime_value": c.lifetime_value,
        "opted_out": c.opted_out,
        "customer_since": c.customer_since.isoformat() if c.customer_since else None,
        "payment_history": payment_history,
        "recovery_history": recovery_history
    }
