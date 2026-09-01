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
                 ┌────────────────┼─────────────────┐
                 │                │                 │
                 ▼                ▼                 ▼
        CUSTOMER ACTION      HUMAN REVIEW      AUTOMATED
           REQUIRED            REQUIRED          RECOVERY
                 │                │                 │
                 ▼                ▼                 ▼
           CUSTOMER NUDGE      ESCALATE          RETRY
                 │                │                 │
                 ▼                │                 ▼
               WAIT               │            GUARDRAILS
                 │                │                 │
                 ▼                │                 ▼
        CUSTOMER FIXED?           │             EXECUTE
           /      \               │                 │
         YES       NO             │                 ▼
          │         │             │              GATEWAY
          ▼         ▼             │                 │
        RETRY      STOP           │                 ▼
          │                        │             SUCCESS?
          │                        │            /       \
          │                        │          YES        NO
          │                        │           │          │
          │                        │           ▼          ▼
          │                        │       RECOVERED  RE-EVALUATING
          │                        │                       │
          └────────────────────────┴───────────────────────┘
                                  │
                                  ▼
                       FRESH DECISION CYCLE
```

### Decision Layers

| Stage            | Question Answered                                      |
| ---------------- | ------------------------------------------------------ |
| **Detect**       | What payment failed and should enter recovery?         |
| **Diagnose**     | Why did the payment fail?                              |
| **ML Inference** | How likely is recovery, and which action is promising? |
| **Prioritize**   | Which case has the highest expected recovery value?    |
| **Decide**       | Retry, wait for customer action, escalate, or stop?    |
| **Guardrails**   | Is the proposed action actually allowed?               |
| **Execute**      | Carry out the permitted action.                        |
| **Observe**      | What actually happened?                                |
| **Re-evaluate**  | What should Revora AI do next?                         |

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

## Root-Cause Diagnosis

Failures are mapped into meaningful operational categories, such as:

```text
TRANSIENT_FAILURE
CUSTOMER_ACTION_REQUIRED
RISK_RELATED
PAYMENT_INSTRUMENT
GATEWAY_ERROR
```

with diagnostic confidence.

## Action Prediction

The action model uses a trained `HistGradientBoostingClassifier` and `predict_proba()` to dynamically estimate the probability of:

```text
RETRY
CUSTOMER_NUDGE
HUMAN_REVIEW
STOP
```

rather than relying on fixed action outputs.

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

### Automated Retry

For suitable transient failures:

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

### Customer Action

For customer-dependent failures:

```text
CARD_EXPIRED
        ↓
CUSTOMER_ACTION_REQUIRED
        ↓
UPDATE_CARD
        ↓
Customer Nudge
        ↓
Wait
        ↓
Customer Resolves
        ↓
Re-evaluate
        ↓
Retry
```

Examples include expired cards, insufficient funds, and payment-method issues.

### Human Review

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

Human approval itself is not considered payment recovery.

### Stop

Cases that should not continue through automated recovery move to:

```text
STOPPED
```

with the appropriate policy reason preserved.

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

This creates a **closed-loop recovery system** capable of adapting after each outcome.

---

# Scheduled Recovery

When an action cannot be executed yet, Revora AI persists a backend-controlled `retry_after` timestamp.

```text
Retry requested
      ↓
Retry not yet eligible
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

The frontend displays timing information, while the backend remains responsible for execution.

This allows the system to continue operating even when the browser is no longer open.

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
```

> **AI recommends. Policy validates. The system executes.**

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

Recovered cases leave the active operational queue and remain available through a dedicated **Recovered** view.

The underlying case remains stored for history and analytics.

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

Revora AI provides dedicated operational views for:

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

Production CORS is restricted to trusted frontend origins rather than using a wildcard origin.

---

# Simulation & Demo Environment

Revora AI provides a controlled payment simulation environment for demonstrating the complete recovery lifecycle without requiring live financial transactions.

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

This makes the end-to-end system demonstrable in a controlled environment.

---

# Technology Stack

| Layer              | Technology                     |
| ------------------ | ------------------------------ |
| Frontend           | React, TypeScript, Vite        |
| Backend            | Python, FastAPI                |
| Database           | SQLite, SQLAlchemy             |
| Machine Learning   | scikit-learn                   |
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
│   └── tests/
│
├── frontend/
│   └── src/
│
├── recoverai.db
└── README.md
```

---

# Local Setup

## Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
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

The system includes automated verification for:

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

The latest complete verification reported:

```text
71 tests passed
0 failed
```

with a successful frontend production build.

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
