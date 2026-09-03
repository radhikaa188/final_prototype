# Revora AI

### AI-Powered Autonomous Revenue Recovery for Failed Payments

> **Recover the right payment, at the right time, with the right action.**

Revora AI is an intelligent revenue-recovery platform that transforms failed payments into prioritized, explainable, and actionable recovery workflows.

It combines **machine learning, expected-value prioritization, deterministic policy guardrails, automated execution, customer intervention, human review, and closed-loop re-evaluation** to turn failed payments into structured recovery opportunities.

---

## The Problem

A failed payment does not always require the same response.

Some payments are highly recoverable and should be retried.
Some require the customer to update a card or add funds.
Some require operational review.
Others should be stopped.

The challenge is not simply detecting failure.

The challenge is deciding:

> **What should we do next, when should we do it, and is it safe to do so?**

Revora AI is built to answer exactly that.

---

# Core Recovery Workflow

Revora AI follows a **multi-stage, closed-loop recovery workflow** where every stage contributes to the final decision.

```text
                         PAYMENT FAILURE
                                │
                                ▼
                       ┌─────────────────┐
                       │      DETECT     │
                       │ Ingest + Dedup  │
                       └────────┬────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │     DIAGNOSE    │
                       │ Failure Reason  │
                       │ Root Cause      │
                       │ Confidence      │
                       └────────┬────────┘
                                │
                                ▼
                  ┌────────────────────────────┐
                  │       ML INFERENCE         │
                  │                            │
                  │ P(Recovery)                │
                  │ Action Probabilities       │
                  │ Expected Recovery          │
                  └─────────────┬──────────────┘
                                │
                                ▼
                  ┌────────────────────────────┐
                  │        PRIORITIZE          │
                  │                            │
                  │ Revenue at Risk            │
                  │ × P(Recovery)              │
                  │ = Expected Recovery        │
                  └─────────────┬──────────────┘
                                │
                                ▼
                  ┌────────────────────────────┐
                  │          DECIDE            │
                  │                            │
                  │ What should happen next?   │
                  └─────────────┬──────────────┘
                                │
             ┌──────────────────┼──────────────────┐
             │                  │                  │
             ▼                  ▼                  ▼
      CUSTOMER ACTION       HUMAN REVIEW       AUTOMATED
         REQUIRED             REQUIRED          RECOVERY
             │                  │                  │
             ▼                  ▼                  ▼
       CUSTOMER NUDGE        ESCALATE            RETRY
             │                  │                  │
             ▼                  │                  ▼
            WAIT                │             GUARDRAILS
             │                  │                  │
             ▼                  │                  ▼
    CUSTOMER ACTION             │              EXECUTE
       COMPLETED?               │                  │
        /      \                │                  ▼
      YES       NO              │               GATEWAY
       │         │              │                  │
       ▼         │              │                  ▼
   RE-EVALUATE   │              │              SUCCESS?
       │         │              │             /       \
       ▼         │              │           YES        NO
     RETRY       │              │            │          │
       │         │              │            ▼          ▼
       ▼         │              │        RECOVERED  RE-EVALUATING
     SUCCESS     │              │                       │
       │         │              │                       │
       └─────────┴──────────────┴───────────────────────┘
                                │
                                ▼
                         FRESH DECISION CYCLE
```

### Decision Layers

| Stage            | Question Answered                                      |
| ---------------- | ------------------------------------------------------ |
| **Detect**       | What payment failed and should enter recovery?         |
| **Diagnose**     | What does the gateway failure information indicate?    |
| **ML Inference** | How likely is recovery, and which action is promising? |
| **Prioritize**   | Which case has the highest expected recovery value?    |
| **Decide**       | What should Revora do next?                            |
| **Guardrails**   | Is the proposed action actually allowed?               |
| **Execute**      | Carry out the permitted action.                        |
| **Observe**      | What actually happened?                                |
| **Re-evaluate**  | What should Revora do after the new outcome?           |

This architecture makes recovery **adaptive rather than one-shot**.

---

# Recovery Intelligence

## Recovery Probability

Revora AI uses a trained machine-learning model to estimate:

```text
P(Recovery)
```

for each failed payment.

The probability becomes a key signal for prioritization and recovery decision-making.

The model uses payment and customer context rather than relying on a fixed recovery percentage.

---

## Root-Cause Diagnosis

Payment gateways provide failure information such as decline reasons and response codes.

Revora AI interprets that information into meaningful operational categories, including:

```text
TRANSIENT_FAILURE
CUSTOMER_ACTION_REQUIRED
RISK_RELATED
PAYMENT_INSTRUMENT
GATEWAY_ERROR
```

Each diagnosis is accompanied by a confidence value.

This allows the recovery system to distinguish between failures that may recover automatically and failures that require customer or operational intervention.

---

## Action Prediction

Revora AI uses a trained `HistGradientBoostingClassifier` with `predict_proba()` to dynamically estimate the likelihood of:

```text
RETRY
CUSTOMER_NUDGE
HUMAN_REVIEW
STOP
```

The action model considers multiple payment, customer, recovery, and diagnostic features instead of relying on a single hardcoded failure-to-action mapping.

The resulting recommendation is then evaluated by deterministic policy guardrails before execution.

---

# Expected-Value Prioritization

Revora AI does not prioritize payments solely by transaction amount.

It combines financial exposure with recovery likelihood:

```text
Revenue at Risk × P(Recovery)
              ↓
      Expected Recovery
              ↓
       Priority Score
```

This creates a queue focused on **expected business impact**.

### Example

```text
Payment A
$2,000 × 20%
= $400 expected recovery

Payment B
$700 × 85%
= $595 expected recovery
```

Although Payment A is larger, Payment B represents the stronger recovery opportunity.

---

# Intelligent Recovery Paths

## Automated Retry

For suitable failures:

```text
Failure
  ↓
ML Recommendation
  ↓
Priority
  ↓
Guardrails
  ↓
Retry
  ↓
Gateway
  ↓
Success → RECOVERED
```

A retry is never executed solely because the ML model recommends it. Deterministic guardrails independently validate the action first.

---

## Customer Action

For customer-dependent failures:

```text
CARD_EXPIRED
        ↓
CUSTOMER_ACTION_REQUIRED
        ↓
UPDATE_CARD
        ↓
CUSTOMER NUDGE
        ↓
WAIT
        ↓
CUSTOMER COMPLETES ACTION
        ↓
RE-EVALUATE
        ↓
GUARDRAILS
        ↓
RETRY
```

Examples include:

* Expired cards
* Invalid payment methods
* Insufficient funds
* Authentication requirements
* Mandate authorization

### Important distinction

```text
CUSTOMER_ACTION_REQUIRED
=
The customer must fix something.

CUSTOMER_NUDGE
=
The system communicates the required action.

HUMAN_REVIEW
=
Operations must investigate or decide.
```

Revora does **not** automatically mark a customer action as completed.

The system waits for an actual customer-action completion event. In Test Mode, this can be represented through a controlled simulated customer event.

---

# Human Review

Risk-sensitive or ambiguous cases can be escalated:

```text
Risk / Exception
      ↓
ESCALATED
      ↓
Human Review
      ↓
Decision
      ↓
Recovery Action
```

Examples include:

* Suspicious or fraud-like activity
* High-risk payments
* Very high-value payments
* Repeated failures
* Policy exceptions
* Cases requiring manual investigation

Human review itself is **not** considered payment recovery.

The case becomes `RECOVERED` only after the underlying payment actually succeeds.

---

# Stop

Cases that should not continue through automated recovery move to:

```text
STOPPED
```

with the appropriate policy reason preserved.

Examples include:

```text
Maximum retry limit reached
Fraud / risk restriction
Customer-action window expired
Policy hard stop
```

A stopped case does not automatically retry unless the existing system explicitly provides a controlled reopening mechanism.

---

# Closed-Loop Re-evaluation

A failed recovery attempt does not automatically end the case.

```text
RETRY
  ↓
FAILED
  ↓
RE_EVALUATING
  ↓
Fresh Context
  ↓
Fresh ML Inference
  ↓
Fresh Policy Evaluation
  ↓
Next Decision
```

The next cycle can result in:

```text
RETRY
CUSTOMER_ACTION_REQUIRED
ESCALATED
STOPPED
RECOVERED
```

Each re-evaluation uses the **current case state and fresh context**, rather than blindly repeating the previous action.

---

# Scheduled Recovery

When an action is not yet eligible for execution, Revora AI persists a backend-controlled `retry_after` timestamp.

```text
Retry Requested
      ↓
Retry Not Yet Eligible
      ↓
Scheduled
      ↓
Countdown
      ↓
Backend Scheduler
      ↓
Fresh Re-evaluation
      ↓
Guardrails
      ↓
Execution
```

The frontend displays timing information, while the backend remains responsible for determining when execution is permitted.

This allows scheduled recovery to continue even when the browser is no longer open.

---

# Customer-Action Waiting

Customer-dependent cases follow a different lifecycle.

```text
CUSTOMER_ACTION_REQUIRED
          ↓
CUSTOMER NUDGE
          ↓
WAIT
          ↓
Customer Completes Required Action
          ↓
Completion Event
          ↓
RE-EVALUATE
          ↓
Fresh ML + Policy Decision
          ↓
Retry / Escalate / Stop
```

There is **no automatic retry while the required customer action remains incomplete**.

If the customer does not resolve the issue before the configured recovery window expires:

```text
CUSTOMER_ACTION_REQUIRED
          ↓
WINDOW EXPIRED
          ↓
STOPPED
```

This prevents the system from repeatedly attempting a payment that still requires customer intervention.

---

# Deterministic Guardrails

Machine learning provides intelligence.

**Policy provides authority.**

The system keeps deterministic guardrails between recommendation and execution:

```text
ML Recommendation
       ↓
Policy Validation
       ↓
Allowed / Blocked
       ↓
Execution
```

Guardrails can enforce:

```text
Retry limits
Recovery-window constraints
Customer opt-out
Automatic recovery amount limits
Risk restrictions
Duplicate execution protection
Current payment state
Customer-action requirements
```

> **AI recommends. Policy validates. The system executes.**

The ML or action model cannot override deterministic safety policies.

---

# Explicit Recovery States

Revora AI distinguishes between different operational outcomes:

```text
PRIORITIZED
CUSTOMER_ACTION_REQUIRED
RE_EVALUATING
ESCALATED
STOPPED
RECOVERED
```

This prevents fundamentally different situations from being represented by the same state.

For example:

```text
CUSTOMER_ACTION_REQUIRED
=
Customer must fix something
```

while:

```text
ESCALATED
=
Operations must investigate or decide
```

and:

```text
RECOVERED
=
Payment actually succeeded
```

---

# Recovery Queue

The Recovery Queue is the primary operational worklist.

Active cases are ranked using the ML-driven priority score.

Typical active states include:

```text
PRIORITIZED
CUSTOMER_ACTION_REQUIRED
ESCALATED
RE_EVALUATING
```

Recovered cases leave the active operational queue while remaining available for historical reporting and analytics.

The underlying recovery case remains persistent throughout its lifecycle.

---

# Agent Operations

Agent Operations answers:

> **What did the recovery agent do?**

It provides execution-level visibility into:

```text
Agent Runs
Agent Steps
Diagnosis
ML Predictions
Action Selection
Guardrails
Execution
Recovery Outcome
```

A completed workflow does not automatically mean a successful payment recovery.

```text
WORKFLOW COMPLETED ≠ PAYMENT RECOVERED
```

Actual recovery is represented by the payment and recovery-case state.

---

# Audit Trail

Audit Trail answers:

> **What happened to this case over time?**

It captures the broader operational timeline:

```text
Payment Events
Webhook Events
State Changes
Agent Decisions
Human Actions
Notifications
Policy Events
Recovery Events
```

The distinction is:

```text
Agent Operations
→ How the agent processed the case

Audit Trail
→ Complete chronological case history
```

---

# Data & Correlation Model

Revora AI keeps persistent business identity separate from execution identity.

```text
Customer
   │
   ├── Payment
   │      │
   │      └── RecoveryCase
   │               ├── AgentRuns
   │               ├── RecoveryActions
   │               └── AuditEvents
```

A recovery case remains the same business case throughout transitions such as:

```text
PRIORITIZED
→ RE_EVALUATING
→ RETRY
→ RECOVERED
```

Individual `AgentRun` and `RecoveryAction` identifiers may change because each execution is a separate attempt.

This provides stable case-level correlation while preserving execution-level history.

---

# Terminal Recovery Invariant

Revora AI treats successful payment recovery as a terminal business outcome.

```text
Payment.status == SUCCESS
        ↓
RecoveryCase = RECOVERED
        ↓
next_action = NONE
        ↓
No further automatic execution
```

A recovered case must never:

* Become `STOPPED`
* Become `ESCALATED`
* Enter `CUSTOMER_ACTION_REQUIRED`
* Receive another automatic retry
* Receive another recovery execution

This ensures that **recovery represents an actual successful payment**, not merely an attempted action.

---

# Analytics

Revora AI converts operational recovery activity into financial intelligence.

### Core Metrics

```text
Revenue At Risk
Recoverable Revenue
Revenue Recovered
Recovery Rate
Active Cases
Recovered Cases
```

### Recovery Funnel

```text
Failed Payments
      ↓
Recovery Cases
      ↓
Eligible Cases
      ↓
Actioned Cases
      ↓
Recovered Cases
```

The analytics layer uses persisted backend data so operational metrics remain connected to the recovery workflow.

---

# Operations Dashboard

Revora AI provides dedicated operational views:

| View                 | Purpose                                |
| -------------------- | -------------------------------------- |
| **Command Center**   | Executive recovery overview            |
| **Recovery Queue**   | Prioritized recovery workload          |
| **Case Detail**      | Full case intelligence and lifecycle   |
| **Agent Operations** | Agent execution history                |
| **Human Review**     | Operations intervention queue          |
| **Customer Actions** | Customer-dependent recovery cases      |
| **Customers**        | Customer-level recovery information    |
| **Payments**         | Payment ledger and lifecycle           |
| **Analytics**        | Financial and operational intelligence |
| **Audit Trail**      | Chronological traceability             |
| **Policies**         | Recovery policy configuration          |
| **Test Mode**        | Controlled payment simulation          |

---

# Customer & Payment Intelligence

### Customer View

```text
Customer ID
Name
Email
Lifetime Value
Successful Payments
Failed Payments
Recovered Revenue
Opt-Out Status
```

### Payment View

```text
Payment ID
Gateway Payment ID
Customer
Amount
Failure Reason
Attempt Number
Status
```

### Recovery Case View

```text
Case ID
Priority
Recovery Probability
Root Cause
Recommended Action
Current State
Recovery Outcome
```

---

# Security

Revora AI uses backend-controlled authentication and authorization.

Key practices include:

```text
JWT Authentication
Role-Based Access
bcrypt Password Verification
Environment-Based Secrets
Explicit CORS Origins
Webhook Secret Configuration
Backend-Only Credentials
```

Production CORS is restricted to explicitly trusted frontend origins rather than using a wildcard origin.

Sensitive credentials are kept on the backend and are not exposed through frontend configuration.

---

# Simulation & Demo Environment

Revora AI provides a controlled payment simulation environment for demonstrating the recovery lifecycle without requiring live financial transactions.

A simulated payment can move through:

```text
FAILED
  ↓
DIAGNOSE
  ↓
ML
  ↓
PRIORITIZE
  ↓
DECIDE
  ↓
GUARDRAILS
  ↓
EXECUTE
  ↓
SUCCESS / FAILURE
  ↓
RECOVERED / RE-EVALUATING
```

Customer-dependent scenarios can additionally demonstrate:

```text
CUSTOMER_ACTION_REQUIRED
        ↓
CUSTOMER NUDGE
        ↓
WAIT
        ↓
CUSTOMER ACTION COMPLETED
        ↓
RE-EVALUATE
        ↓
RETRY
        ↓
RECOVERED
```

This provides a controlled way to demonstrate the complete system behavior.

---

# Technology Stack

| Layer              | Technology                     |
| ------------------ | ------------------------------ |
| Frontend           | React, TypeScript, Vite        |
| Backend            | Python, FastAPI                |
| Database           | SQLite, SQLAlchemy             |
| Machine Learning   | scikit-learn                   |
| Recovery Model     | RandomForestClassifier         |
| Action Model       | HistGradientBoostingClassifier |
| Authentication     | JWT, bcrypt                    |
| API                | REST                           |
| Payment Simulation | Gateway Simulator              |
| Scheduling         | FastAPI Background Scheduler   |
| Testing            | pytest                         |
| Deployment         | Vercel + Render                |

---

# Project Structure

```text
Revora-AI/
│
├── backend/
│   ├── app/
│   ├── data/
│   └── tests/
│
├── frontend/
│   └── src/
│
├── README.md
└── .gitignore
```

Runtime artifacts, local databases, generated build output, and dependency directories should remain outside source control where appropriate.

---

# Local Setup

## Backend

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

## Frontend

```bash
cd frontend
npm install
npm run dev
```

## Run Tests

```bash
cd backend
python -m pytest tests/ -v
```

## Production Build

```bash
cd frontend
npm run build
```

---

# Deployment

```text
Frontend → Vercel
Backend  → Render
```

The frontend communicates with the FastAPI backend through the configured API URL.

Sensitive backend credentials belong in the backend environment and should never be exposed through frontend configuration.

---

# Verification

The project includes automated verification covering:

```text
ML inference
Recovery probability
Action prediction
Guardrails
Customer Action lifecycle
Human Review
Scheduled retries
Re-evaluation
Queue prioritization
Business correlation
Terminal recovery states
Authentication
CORS
Notifications
Audit behavior
```

The verification suite is designed to validate both individual components and end-to-end recovery behavior.

---

# Why Revora AI?

Revora AI brings multiple layers of payment recovery into one decision system:

```text
Machine Learning
        +
Expected-Value Prioritization
        +
Policy Guardrails
        +
Automated Recovery
        +
Customer Intervention
        +
Human Escalation
        +
Closed-Loop Re-evaluation
        +
Operational Analytics
        +
Auditability
```

Instead of simply asking:

> **“Did the payment fail?”**

Revora AI asks:

> **“What is the recovery opportunity?”**

> **“What should we do next?”**

> **“Is that action allowed?”**

> **“What should happen if it fails?”**

That is the difference between a retry script and an intelligent revenue-recovery system.

---

# Vision

> **Revenue recovery should be an intelligent decision system — not a blind retry mechanism.**

### Revora AI

**Detect. Diagnose. Prioritize. Decide. Recover.**
