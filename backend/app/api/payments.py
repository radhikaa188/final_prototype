from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import Payment, Customer, RecoveryCase

router = APIRouter(prefix="/payments", tags=["payments"])

@router.get("")
def list_payments(
    status: str = Query(None),
    limit: int = Query(100),
    offset: int = Query(0),
    db: Session = Depends(get_db)
):
    query = db.query(Payment)
    if status:
        query = query.filter(Payment.status == status)
    
    total = query.count()
    payments = query.order_by(Payment.created_at.desc()).offset(offset).limit(limit).all()

    res = []
    for p in payments:
        cust = db.query(Customer).filter(Customer.id == p.customer_id).first()
        case = db.query(RecoveryCase).filter(RecoveryCase.payment_id == p.id).first()
        res.append({
            "id": p.id,
            "gateway_payment_id": p.gateway_payment_id,
            "customer_id": p.customer_id,
            "customer_name": cust.name if cust else "Unknown",
            "amount": p.amount,
            "currency": p.currency,
            "status": p.status,
            "failure_reason": p.failure_reason,
            "failure_category": p.failure_category,
            "attempt_number": p.attempt_number,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "recovery_case_id": case.id if case else None,
            "recovery_case_status": case.status if case else None
        })

    return {"total": total, "payments": res}

@router.get("/{payment_id}")
def get_payment_detail(payment_id: str, db: Session = Depends(get_db)):
    p = db.query(Payment).filter(Payment.id == payment_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    cust = db.query(Customer).filter(Customer.id == p.customer_id).first()
    case = db.query(RecoveryCase).filter(RecoveryCase.payment_id == p.id).first()

    return {
        "id": p.id,
        "gateway_payment_id": p.gateway_payment_id,
        "customer": {
            "id": cust.id if cust else None,
            "name": cust.name if cust else None,
            "email": cust.email if cust else None,
            "ltv": cust.lifetime_value if cust else 0.0
        },
        "amount": p.amount,
        "currency": p.currency,
        "status": p.status,
        "failure_reason": p.failure_reason,
        "failure_category": p.failure_category,
        "attempt_number": p.attempt_number,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "recovery_case": {
            "id": case.id if case else None,
            "status": case.status if case else None,
            "expected_recovery": case.expected_recovery if case else None,
            "priority_score": case.priority_score if case else None
        } if case else None
    }
