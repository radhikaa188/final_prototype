import json
from datetime import datetime, timezone
from typing import Dict, Any
from sqlalchemy.orm import Session
from app.db.models import AuditEvent

class AuditService:
    @staticmethod
    def record_event(
        db: Session,
        event_type: str,
        actor_type: str,
        description: str,
        case_id: str = None,
        agent_run_id: str = None,
        metadata: Dict[str, Any] = None
    ) -> AuditEvent:
        event = AuditEvent(
            case_id=case_id,
            agent_run_id=agent_run_id,
            event_type=event_type,
            actor_type=actor_type, # SYSTEM, ML, AGENT, POLICY_ENGINE, EXECUTOR, HUMAN, GATEWAY
            description=description,
            metadata_json=json.dumps(metadata) if metadata else None,
            created_at=datetime.now(timezone.utc)
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event

audit_service = AuditService()
