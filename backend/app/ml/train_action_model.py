import os
import json
import numpy as np
import pandas as pd
import joblib
from datetime import datetime
from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, classification_report
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(SCRIPT_DIR, "..", "..", "data", "recovery_action_training.csv")
SAVED_MODELS_DIR = os.path.join(SCRIPT_DIR, "saved_models")
METRICS_JSON_PATH = os.path.join(SCRIPT_DIR, "action_model_metrics.json")

os.makedirs(SAVED_MODELS_DIR, exist_ok=True)

def train_and_evaluate_action_model():
    print("=====================================================================")
    print("   RECOVERAI — ML ACTION SELECTION MODEL TRAINING PIPELINE           ")
    print("=====================================================================")

    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(f"Training dataset not found at {DATA_PATH}")

    df = pd.read_csv(DATA_PATH)
    print(f"[Dataset] Loaded {len(df)} rows and {len(df.columns)} columns from recovery_action_training.csv")

    # Target class distribution
    target_counts = df['recommended_action'].value_counts().to_dict()
    print("[Target Distribution]", target_counts)

    # Sort chronologically by payment_date
    df['payment_date_dt'] = pd.to_datetime(df['payment_date'])
    df = df.sort_values('payment_date_dt').reset_index(drop=True)

    # Chronological Split (80% Train, 20% Test)
    split_idx = int(len(df) * 0.80)
    train_df = df.iloc[:split_idx].copy()
    test_df = df.iloc[split_idx:].copy()

    print(f"[Data Split] Chronological Split by payment_date:")
    print(f"  - Training Set: {len(train_df)} rows (Dates: {train_df['payment_date'].min()} to {train_df['payment_date'].max()})")
    print(f"  - Testing Set : {len(test_df)} rows (Dates: {test_df['payment_date'].min()} to {test_df['payment_date'].max()})")

    # Feature Space Definition
    numeric_features = [
        'amount_usd', 'attempt_number', 'previous_failures',
        'days_since_last_payment', 'historical_success_rate',
        'customer_tenure_months', 'monthly_charge_usd', 'support_ticket_count',
        'customer_lifetime_value_usd', 'recovery_probability',
        'root_cause_confidence', 'revenue_at_risk', 'expected_recovery'
    ]

    categorical_features = [
        'failure_reason', 'gateway_response_code', 'payment_method', 'root_cause'
    ]

    boolean_features = ['customer_opted_out']

    # Preprocessing
    for b_feat in boolean_features:
        train_df[b_feat] = train_df[b_feat].astype(int)
        test_df[b_feat] = test_df[b_feat].astype(int)

    all_feature_cols = numeric_features + categorical_features + boolean_features
    X_train = train_df[all_feature_cols]
    y_train = train_df['recommended_action']
    X_test = test_df[all_feature_cols]
    y_test = test_df['recommended_action']

    preprocessor = ColumnTransformer(
        transformers=[
            ('num', StandardScaler(), numeric_features),
            ('cat', OneHotEncoder(handle_unknown='ignore', sparse_output=False), categorical_features),
            ('bool', 'passthrough', boolean_features)
        ]
    )

    print("\n[Preprocessor] Fitting ColumnTransformer on Training set...")
    X_train_proc = preprocessor.fit_transform(X_train)
    X_test_proc = preprocessor.transform(X_test)

    # Models to Evaluate
    models = {
        "RandomForestClassifier": RandomForestClassifier(n_estimators=200, max_depth=12, random_state=42, n_jobs=-1),
        "HistGradientBoostingClassifier": HistGradientBoostingClassifier(max_iter=200, max_depth=8, random_state=42),
        "LogisticRegression": LogisticRegression(max_iter=1000, random_state=42)
    }

    best_model = None
    best_model_name = ""
    best_macro_f1 = -1.0
    results = {}

    target_labels = ['RETRY', 'CUSTOMER_NUDGE', 'HUMAN_REVIEW', 'STOP']

    for name, model in models.items():
        print(f"\n[Training] Fitting {name}...")
        model.fit(X_train_proc, y_train)
        y_pred = model.predict(X_test_proc)

        acc = accuracy_score(y_test, y_pred)
        macro_f1 = f1_score(y_test, y_pred, average='macro')
        weighted_f1 = f1_score(y_test, y_pred, average='weighted')

        prec_per_class = precision_score(y_test, y_pred, average=None, labels=target_labels)
        rec_per_class = recall_score(y_test, y_pred, average=None, labels=target_labels)
        f1_per_class = f1_score(y_test, y_pred, average=None, labels=target_labels)
        cm = confusion_matrix(y_test, y_pred, labels=target_labels)

        per_class_metrics = {}
        for idx, lbl in enumerate(target_labels):
            per_class_metrics[lbl] = {
                "precision": round(float(prec_per_class[idx]), 4),
                "recall": round(float(rec_per_class[idx]), 4),
                "f1": round(float(f1_per_class[idx]), 4)
            }

        results[name] = {
            "accuracy": round(float(acc), 4),
            "macro_f1": round(float(macro_f1), 4),
            "weighted_f1": round(float(weighted_f1), 4),
            "per_class": per_class_metrics,
            "confusion_matrix": cm.tolist()
        }

        print(f"  {name} Results -> Accuracy: {acc*100:.2f}%, Macro F1: {macro_f1:.4f}, Weighted F1: {weighted_f1:.4f}")

        if macro_f1 > best_macro_f1:
            best_macro_f1 = macro_f1
            best_model_name = name
            best_model = model

    print("\n=====================================================================")
    print(f"   BEST ACTION SELECTION MODEL: {best_model_name}")
    print(f"   Macro F1: {best_macro_f1:.4f} | Accuracy: {results[best_model_name]['accuracy']*100:.2f}%")
    print("=====================================================================")

    # Print Detailed Per-Class Performance
    best_res = results[best_model_name]
    print("\nPer-Class Performance Report:")
    print(f"{'Class':<20} | {'Precision':<10} | {'Recall':<10} | {'F1-Score':<10}")
    print("-" * 60)
    for lbl in target_labels:
        m = best_res["per_class"][lbl]
        print(f"{lbl:<20} | {m['precision']:<10.4f} | {m['recall']:<10.4f} | {m['f1']:<10.4f}")

    print("\nConfusion Matrix (Rows=True, Cols=Predicted):")
    print(f"Labels order: {target_labels}")
    for row in best_res["confusion_matrix"]:
        print("  ", row)

    # Persist Selected Model and Preprocessor
    model_path = os.path.join(SAVED_MODELS_DIR, "action_model.joblib")
    preproc_path = os.path.join(SAVED_MODELS_DIR, "action_preprocessor.joblib")

    joblib.dump(best_model, model_path)
    joblib.dump(preprocessor, preproc_path)
    print(f"\n[Artifacts Saved]")
    print(f"  - Model Path       : {model_path}")
    print(f"  - Preprocessor Path: {preproc_path}")

    # Save Metrics JSON Metadata
    metrics_payload = {
        "model_name": best_model_name,
        "trained_at": datetime.now().isoformat(),
        "dataset_rows": len(df),
        "train_rows": len(train_df),
        "test_rows": len(test_df),
        "target_classes": target_labels,
        "features_used": all_feature_cols,
        "accuracy": best_res["accuracy"],
        "macro_f1": best_res["macro_f1"],
        "weighted_f1": best_res["weighted_f1"],
        "per_class_metrics": best_res["per_class"],
        "confusion_matrix": best_res["confusion_matrix"],
        "all_model_evaluations": {
            k: {"accuracy": v["accuracy"], "macro_f1": v["macro_f1"], "weighted_f1": v["weighted_f1"]}
            for k, v in results.items()
        }
    }

    with open(METRICS_JSON_PATH, "w") as f:
        json.dump(metrics_payload, f, indent=2)
    print(f"  - Metrics Artifact : {METRICS_JSON_PATH}")
    print("=====================================================================")

if __name__ == "__main__":
    train_and_evaluate_action_model()
