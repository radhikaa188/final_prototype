from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.db.session import Base

def generate_uuid():
    return str(uuid.uuid4())

def utc_now():
    return datetime.now(timezone.utc)

class Customer(Base):
    __tablename__ = "customers"

    id = Column(String, primary_key=True, default=generate_uuid)
    external_customer_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    customer_since = Column(DateTime, default=utc_now)
    lifetime_value = Column(Float, default=0.0)
    opted_out = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utc_now)

    payments = relationship("Payment", back_populates="customer")
    recovery_cases = relationship("RecoveryCase", back_populates="customer")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(String, primary_key=True, default=generate_uuid)
    gateway_payment_id = Column(String, unique=True, index=True, nullable=False)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="USD")
    status = Column(String, nullable=False)  # FAILED, SUCCESS, PENDING
    failure_reason = Column(String, nullable=True)
    failure_category = Column(String, nullable=True)
    attempt_number = Column(Integer, default=1)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    customer = relationship("Customer", back_populates="payments")
    recovery_case = relationship("RecoveryCase", back_populates="payment", uselist=False)


class RecoveryCase(Base):
    __tablename__ = "recovery_cases"

    id = Column(String, primary_key=True, default=generate_uuid)
    payment_id = Column(String, ForeignKey("payments.id"), nullable=False, unique=True)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)
    status = Column(String, default="OPEN")  # OPEN, DIAGNOSED, PRIORITIZED, ACTION_PROPOSED, AWAITING_APPROVAL, APPROVED, EXECUTING, RECOVERED, FAILED, RE_EVALUATING, STOPPED, ESCALATED
    revenue_at_risk = Column(Float, nullable=False)
    recovery_probability = Column(Float, default=0.0)
    expected_recovery = Column(Float, default=0.0)
    priority_score = Column(Float, default=0.0)
    root_cause = Column(String, nullable=True)  # TRANSIENT_FAILURE, CUSTOMER_ACTION, RISK_RELATED, OTHER
    root_cause_confidence = Column(Float, default=0.0)
    recommended_action = Column(String, nullable=True)  # RETRY, CUSTOMER_NUDGE, HUMAN_REVIEW, STOP
    agent_confidence = Column(Float, default=0.0)
    retry_count = Column(Integer, default=0)
    next_action = Column(String, nullable=True)

    # Customer Action Required & Lifecycle Metadata
    customer_action_required = Column(Boolean, default=False)
    customer_action_type = Column(String, nullable=True)  # ADD_FUNDS, UPDATE_CARD, UPDATE_PAYMENT_METHOD, COMPLETE_AUTHENTICATION, AUTHORIZE_MANDATE, OTHER
    customer_action_description = Column(Text, nullable=True)
    customer_notified_at = Column(DateTime, nullable=True)
    waiting_since = Column(DateTime, nullable=True)
    retry_after = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    customer_action_status = Column(String, nullable=True)  # PENDING, COMPLETED, EXPIRED, CANCELLED

    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    closed_at = Column(DateTime, nullable=True)

    payment = relationship("Payment", back_populates="recovery_case")
    customer = relationship("Customer", back_populates="recovery_cases")
    agent_runs = relationship("AgentRun", back_populates="recovery_case")
    recovery_actions = relationship("RecoveryAction", back_populates="recovery_case")
    notifications = relationship("Notification", back_populates="recovery_case")
    audit_events = relationship("AuditEvent", back_populates="recovery_case")


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id = Column(String, primary_key=True, default=generate_uuid)
    case_id = Column(String, ForeignKey("recovery_cases.id"), nullable=False)
    status = Column(String, default="PENDING")  # PENDING, RUNNING, COMPLETED, FAILED, BLOCKED, ESCALATED
    trigger_type = Column(String, default="AUTOMATIC")  # AUTOMATIC, MANUAL_APPROVE, MANUAL_EXECUTE, HUMAN_OVERRIDE
    agent_version = Column(String, default="v1.0.0")
    recommended_action = Column(String, nullable=True)
    approved = Column(Boolean, default=False)
    approved_by = Column(String, nullable=True)
    final_result = Column(String, nullable=True)
    started_at = Column(DateTime, default=utc_now)
    completed_at = Column(DateTime, nullable=True)
    error = Column(Text, nullable=True)

    recovery_case = relationship("RecoveryCase", back_populates="agent_runs")
    steps = relationship("AgentRunStep", back_populates="agent_run", cascade="all, delete-orphan")


class AgentRunStep(Base):
    __tablename__ = "agent_run_steps"

    id = Column(String, primary_key=True, default=generate_uuid)
    run_id = Column(String, ForeignKey("agent_runs.id"), nullable=False)
    step_number = Column(Integer, nullable=False)
    step_name = Column(String, nullable=False)  # LOAD_CONTEXT, DIAGNOSE, PREDICT_RECOVERY, REVIEW_HISTORY, SELECT_ACTION, CHECK_GUARDRAILS, EXECUTE, OBSERVE, UPDATE_STATE, NOTIFY, AUDIT
    status = Column(String, default="PENDING")  # PENDING, RUNNING, SUCCESS, FAILED, BLOCKED
    input_summary = Column(Text, nullable=True)
    output_summary = Column(Text, nullable=True)
    started_at = Column(DateTime, default=utc_now)
    completed_at = Column(DateTime, nullable=True)
    error = Column(Text, nullable=True)

    agent_run = relationship("AgentRun", back_populates="steps")


class RecoveryAction(Base):
    __tablename__ = "recovery_actions"

    id = Column(String, primary_key=True, default=generate_uuid)
    case_id = Column(String, ForeignKey("recovery_cases.id"), nullable=False)
    agent_run_id = Column(String, ForeignKey("agent_runs.id"), nullable=True)
    action_type = Column(String, nullable=False)  # RETRY, CUSTOMER_NUDGE, HUMAN_REVIEW, STOP
    status = Column(String, nullable=False)  # SUCCESS, FAILED, PENDING, BLOCKED
    reason = Column(Text, nullable=True)
    executed_at = Column(DateTime, default=utc_now)
    result = Column(Text, nullable=True)
    amount_recovered = Column(Float, default=0.0)

    recovery_case = relationship("RecoveryCase", back_populates="recovery_actions")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String, primary_key=True, default=generate_uuid)
    case_id = Column(String, ForeignKey("recovery_cases.id"), nullable=True)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=True)
    type = Column(String, nullable=False)  # PAYMENT_FAILED, NUDGE_SENT, RETRY_SUCCESS, RETRY_FAILED, HUMAN_REVIEW_REQUIRED, RECOVERY_COMPLETED, RECOVERY_STOPPED
    channel = Column(String, default="EMAIL")  # EMAIL, IN_APP, SMS
    status = Column(String, default="SENT")  # SENT, DELIVERED, CLICKED, FAILED
    recipient = Column(String, nullable=False)
    sent_at = Column(DateTime, default=utc_now)
    delivered_at = Column(DateTime, nullable=True)
    clicked_at = Column(DateTime, nullable=True)

    recovery_case = relationship("RecoveryCase", back_populates="notifications")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(String, primary_key=True, default=generate_uuid)
    case_id = Column(String, ForeignKey("recovery_cases.id"), nullable=True)
    agent_run_id = Column(String, ForeignKey("agent_runs.id"), nullable=True)
    event_type = Column(String, nullable=False)
    actor_type = Column(String, nullable=False)  # SYSTEM, ML, AGENT, POLICY_ENGINE, EXECUTOR, HUMAN, GATEWAY
    description = Column(Text, nullable=False)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)

    recovery_case = relationship("RecoveryCase", back_populates="audit_events")


class Policy(Base):
    __tablename__ = "policies"

    id = Column(String, primary_key=True, default="default_policy")
    max_retries = Column(Integer, default=3)
    recovery_window_hours = Column(Integer, default=72)
    max_auto_retry_amount = Column(Float, default=10000.0)
    customer_opt_out_enabled = Column(Boolean, default=True)
    duplicate_action_protection = Column(Boolean, default=True)
    customer_action_wait_hours = Column(Integer, default=24)
    customer_action_expire_hours = Column(Integer, default=72)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id = Column(String, primary_key=True, default=generate_uuid)
    event_id = Column(String, unique=True, index=True, nullable=False)
    event_type = Column(String, nullable=False)
    gateway = Column(String, default="razorpay")
    status = Column(String, default="PROCESSED")  # PROCESSED, IGNORED, FAILED, DUPLICATE
    payload_hash = Column(String, nullable=True)
    received_at = Column(DateTime, default=utc_now)
    processed_at = Column(DateTime, default=utc_now)

