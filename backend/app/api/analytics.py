import os
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.session import get_db
from app.db.models import RecoveryCase, Payment, RecoveryAction, AgentRun, AuditEvent

router = APIRouter(prefix="/analytics", tags=["analytics"])

METRICS_JSON_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ml", "ml_metrics.json")

@router.get("/summary")
def get_analytics_summary(db: Session = Depends(get_db)):
    total_cases = db.query(RecoveryCase).count()
    recovered_cases = db.query(RecoveryCase).filter(RecoveryCase.status == "RECOVERED").count()
    total_at_risk = db.query(func.sum(RecoveryCase.revenue_at_risk)).scalar() or 0.0
    total_recovered = db.query(func.sum(RecoveryAction.amount_recovered)).filter(RecoveryAction.status == "SUCCESS").scalar() or 0.0

    return {
        "total_cases": total_cases,
        "recovered_cases": recovered_cases,
        "recovery_rate": round(recovered_cases / total_cases, 4) if total_cases > 0 else 0.0,
        "total_at_risk": round(total_at_risk, 2),
        "total_recovered": round(total_recovered, 2)
    }

@router.get("/failure-reasons")
def get_revenue_by_failure_reason(db: Session = Depends(get_db)):
    results = db.query(
        RecoveryCase.root_cause,
        func.count(RecoveryCase.id).label("case_count"),
        func.sum(RecoveryCase.revenue_at_risk).label("revenue_at_risk")
    ).group_by(RecoveryCase.root_cause).all()

    res = []
    for cause, count, rev in results:
        res.append({
            "root_cause": cause or "OTHER",
            "count": count,
            "revenue": round(rev or 0.0, 2)
        })
    return res

@router.get("/actions")
def get_revenue_by_action_type(db: Session = Depends(get_db)):
    results = db.query(
        RecoveryAction.action_type,
        func.count(RecoveryAction.id).label("total_attempts"),
        func.sum(RecoveryAction.amount_recovered).label("recovered_amount")
    ).group_by(RecoveryAction.action_type).all()

    res = []
    for action_type, count, recovered in results:
        res.append({
            "action_type": action_type,
            "attempts": count,
            "recovered": round(recovered or 0.0, 2)
        })
    return res

@router.get("/ml-metrics")
def get_ml_performance_metrics(db: Session = Depends(get_db)):
    """
    Returns genuine ML model evaluation metrics loaded from ml_metrics.json artifact.
    NO hardcoded metric numbers!
    """
    if os.path.exists(METRICS_JSON_PATH):
        try:
            with open(METRICS_JSON_PATH, "r") as f:
                metrics = json.load(f)
            
            # Compute live prediction distribution across DB cases
            cases = db.query(RecoveryCase).all()
            predictions = [c.recovery_probability or 0.5 for c in cases]
            metrics["prediction_distribution"] = [
                {"range": "0.0 - 0.2", "count": sum(1 for p in predictions if p < 0.2)},
                {"range": "0.2 - 0.4", "count": sum(1 for p in predictions if 0.2 <= p < 0.4)},
                {"range": "0.4 - 0.6", "count": sum(1 for p in predictions if 0.4 <= p < 0.6)},
                {"range": "0.6 - 0.8", "count": sum(1 for p in predictions if 0.6 <= p < 0.8)},
                {"range": "0.8 - 1.0", "count": sum(1 for p in predictions if p >= 0.8)}
            ]
            return metrics
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error reading ML metrics artifact: {e}")
    
    raise HTTPException(status_code=404, detail="ML evaluation metrics file not found. Run 'python backend/app/ml/train_models.py'.")
