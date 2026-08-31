from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import User
from app.auth.dependencies import get_current_user, require_role
from app.policies.guardrails import policy_engine
from app.services.audit_service import audit_service

router = APIRouter(prefix="/policies", tags=["policies"])

class PolicyUpdateSchema(BaseModel):
    max_retries: int
    recovery_window_hours: int
    max_auto_retry_amount: float
    customer_opt_out_enabled: bool
    duplicate_action_protection: bool

@router.get("")
def get_policy(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    policy = policy_engine.get_active_policy(db)
    return {
        "id": policy.id,
        "max_retries": policy.max_retries,
        "recovery_window_hours": policy.recovery_window_hours,
        "max_auto_retry_amount": policy.max_auto_retry_amount,
        "customer_opt_out_enabled": policy.customer_opt_out_enabled,
        "duplicate_action_protection": policy.duplicate_action_protection,
        "updated_at": policy.updated_at.isoformat() if policy.updated_at else None
    }

@router.put("")
def update_policy(payload: PolicyUpdateSchema, db: Session = Depends(get_db), current_user: User = Depends(require_role(["ADMIN"]))):
    policy = policy_engine.get_active_policy(db)
    policy.max_retries = payload.max_retries
    policy.recovery_window_hours = payload.recovery_window_hours
    policy.max_auto_retry_amount = payload.max_auto_retry_amount
    policy.customer_opt_out_enabled = payload.customer_opt_out_enabled
    policy.duplicate_action_protection = payload.duplicate_action_protection
    db.commit()
    db.refresh(policy)

    operator_label = f"{current_user.name or current_user.email} ({current_user.role})"
    audit_service.record_event(db, "POLICY_UPDATED", "HUMAN", f"Administrator ({operator_label}) updated policy settings: max_retries={policy.max_retries}, max_auto_retry_amount=${policy.max_auto_retry_amount:,.2f}")

    return {
        "id": policy.id,
        "max_retries": policy.max_retries,
        "recovery_window_hours": policy.recovery_window_hours,
        "max_auto_retry_amount": policy.max_auto_retry_amount,
        "customer_opt_out_enabled": policy.customer_opt_out_enabled,
        "duplicate_action_protection": policy.duplicate_action_protection,
        "updated_at": policy.updated_at.isoformat() if policy.updated_at else None
    }
