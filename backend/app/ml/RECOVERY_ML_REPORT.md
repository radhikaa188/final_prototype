# RecoverAI — Complete Recovery ML Retraining Report

**Model Name**: Logistic Regression (Calibrated v2.0)  
**Evaluation Type**: Chronological Held-Out Test Set  
**Primary Dataset**: `payment_failure.csv` (Synthetic Payment Failure Telemetry)  
**Report Generated**: 2026-08-28 08:21:01 UTC

---

## 1. Executive Summary

- **Domain Problem**: Predict $P(\text{Recovery})$ for a payment that has **already failed**, to calculate Expected Recoverable Revenue ($\text{amount} \times P(\text{Recovery})$) and rank recovery actions.
- **Previous Invoice Benchmark**: The previous model trained on general billing invoices (`billing.csv`) achieved a ROC-AUC of $\approx 0.5212$ due to a domain mismatch (general invoices lacked decline telemetry).
- **New Retrained Performance**: Training on synthetic payment-failure telemetry (`payment_failure.csv`) yields **Test ROC-AUC = 0.7830**, **PR-AUC = 0.8736**, and **Test F1 = 0.8428**.
- **Important Disclaimer**: `payment_failure.csv` is synthetic telemetry data. The metrics below demonstrate technical ML pipeline correctness and probability calibration, not real-world production recovery performance.

---

## 2. Dataset Validation & Chronological Split

- **Total Rows**: 22,000
- **Unique Payments**: 22,000 (Duplicates: 0)
- **Unique Subscribers**: 21,534
- **Date Range**: 2025-07-01 to 2026-05-31
- **Target Distribution**:
  - **Recovered ($1$)**: 15,373 (69.88%)
  - **Unrecovered ($0$)**: 6,627 (30.12%)
- **Chronological Split**:
  - **Train Set (70%)**: 15,399 rows (2025-07-01 to 2026-04-21)
  - **Validation Set (15%)**: 3,301 rows (2026-04-21 to 2026-05-22)
  - **Test Set (15%)**: 3,300 rows (2026-05-22 to 2026-05-31)

---

## 3. Data Leakage Checks

- **Excluded Identifiers & Target**: `payment_id`, `subscriber_id`, `payment_date`, and `recovered` were strictly excluded from input feature matrix $X$.
- **Time Safety**: Features represent parameters available at/before the payment failure point.
- **No Target Derivatives**: No post-outcome features were used.

---

## 4. Candidate Model Comparison (Validation Set)

| Candidate Model | Validation Accuracy | Validation F1 | Validation ROC-AUC | Validation Brier Score |
| :--- | ---: | ---: | ---: | ---: |
| **Logistic Regression** | 75.25% | 0.8355 | 0.7669 | 0.1691 |
| **Random Forest** | 74.64% | 0.8345 | 0.7633 | 0.1714 |
| **HistGradientBoosting** | 75.01% | 0.8348 | 0.7613 | 0.1712 |

**Selected Model**: **Logistic Regression** (with Sigmoid Calibration)

---

## 5. Final Held-Out Test Set Performance

| Metric | Test Set Score | Majority Baseline |
| :--- | ---: | ---: |
| **ROC-AUC** | **0.7830** | *N/A* |
| **PR-AUC** | **0.8736** | *N/A* |
| **Accuracy** | **76.24%** | 69.09% |
| **Precision** | **77.64%** | *N/A* |
| **Recall** | **92.15%** | *N/A* |
| **F1-Score** | **0.8428** | 0.8172 |
| **Log Loss** | **0.4986** | *N/A* |
| **Brier Score** | **0.1637** | *N/A* |

---

## 6. Model Comparison: Old vs New

| Attribute | Old General Invoice Model | New Payment Failure Model |
| :--- | :--- | :--- |
| **Primary Dataset** | `billing.csv` (Monthly Invoices) | `payment_failure.csv` (Synthetic Failure Telemetry) |
| **Problem Definition** | Predict if general bill gets paid | Predict if failed payment can be recovered |
| **Test ROC-AUC** | **0.5212** (Near Random) | **0.7830** |
| **Test PR-AUC** | 0.9536 (Unbalanced artifact) | **0.8736** |
| **Test Brier Score** | 0.1850 | **0.1637** |
| **Suitability for Agent** | Unsuitable | **Highly Suitable** |

---

## 7. Operational Disclaimer & Limitations

> **IMPORTANT**: `payment_failure.csv` is a synthetic dataset. The model performance metrics demonstrate technical machine learning correctness, probability estimation, and end-to-end integration, not real-world payment recovery performance. Real-world deployment requires training on production gateway decline logs.
