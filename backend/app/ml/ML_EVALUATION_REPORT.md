# RecoverAI — Genuine ML Model Evaluation Report

**Evaluation Type**: Chronological Held-Out Test Set  
**Dataset**: Prototype Dataset (`subscribers.csv`, `billing.csv`, `support_tickets.csv`)  
**Trained At**: 2026-08-28 07:49:46 UTC

---

## 1. Dataset Breakdown & Chronological Split

- **Total Subscribers**: 2,000
- **Total Billing Records**: 15,000
- **Date Range**: 2025-07 to 2026-05
- **Chronological Split Cutoff**: Training (< `2026-05`) vs Test (>= `2026-05`)
- **Training Rows**: 11,758 (78.4%)
- **Held-Out Test Rows**: 3,242 (21.6%)

---

## 2. Target Variable Mapping

- **Positive Class (1 = Recovered)**: `Paid On Time`, `Paid Late` (14,281 rows, 95.21%)
- **Negative Class (0 = Unrecovered)**: `Failed`, `Unpaid` (719 rows, 4.79%)
- **Data Leakage Check**: `payment_status` and `days_to_payment` were strictly excluded from input feature matrix $X$.

---

## 3. Feature Pipeline

- **Numeric Features (16)**: `['total_billed_usd', 'base_charge_usd', 'data_overage_usd', 'intl_roaming_usd', 'tax_usd', 'late_fee_usd', 'tenure_months', 'age', 'contract_months', 'monthly_charge_usd', 'device_age_months', 'num_lines', 'ticket_count', 'avg_resolution_hours', 'avg_satisfaction', 'escalation_count']`
- **Categorical Features (10)**: `['plan_type', 'payment_method', 'device_type', 'acquisition_channel', 'gender', 'area_type', 'has_family_plan', 'has_internet', 'has_streaming_bundle', 'has_device_protection']`
- **Time-Safe Support Features**: Only tickets occurring before the billing date were aggregated per subscriber.

---

## 4. Model Architecture & Hyperparameters

- **Algorithm**: `RandomForestClassifier`
- **Hyperparameters**: `n_estimators=200`, `max_depth=10`, `class_weight='balanced'`, `random_state=42`
- **Preprocessor**: `ColumnTransformer` with `StandardScaler` (numeric) + `OneHotEncoder` (categorical)

---

## 5. Held-Out Test Set Performance

| Metric | Value |
| :--- | ---: |
| **Accuracy** | **76.34%** |
| **Precision** | **94.86%** |
| **Recall** | **79.32%** |
| **F1-Score** | **0.8639** |
| **ROC-AUC** | **0.5212** |
| **PR-AUC** | **0.9536** |
| **Log Loss** | **0.5529** |
| **Brier Score** | **0.1850** |

### Confusion Matrix
```
               Predicted 0    Predicted 1
Actual 0 (Unrec)   40           132         
Actual 1 (Rec)     635          2435        
```

---

## 6. Baseline Comparison

- **Majority Class Baseline Accuracy**: 94.69%
- **ML Model Accuracy**: 76.34%
- **Net Accuracy Improvement**: +-18.35%

---

## 7. Operational Disclaimer

> **IMPORTANT**: The dataset used for training and evaluation is a prototype dataset. Performance metrics demonstrate technical machine learning correctness and pipeline functionality, not real-world revenue recovery performance.
