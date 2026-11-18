"""
Trains the exception-merit model: given a flagged design-system violation,
predict the probability it deserves to be approved as a legitimate exception
versus auto-fixed back to the token/component library.

Model: soft-voting ensemble (RandomForest + GradientBoosting + Logistic
Regression) - same substitution pattern as PaymentGuard, since this sandbox
has no network access to install XGBoost.
"""
import json
import sqlite3
import pickle
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, VotingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score, precision_score, recall_score, f1_score

DB_PATH = "/home/claude/designguard/designguard.db"
MODEL_PATH = "/home/claude/designguard/models/risk_model.pkl"

FEATURE_COLUMNS = [
    "deviation", "prior_exceptions_count", "is_high_visibility",
    "type_off_palette_color", "type_non_standard_spacing", "type_duplicate_component",
    "type_inconsistent_corner_radius", "type_unapproved_font_size",
    "sev_cosmetic", "sev_moderate", "sev_brand_critical",
]


def load_dataframe():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM design_elements", conn)
    conn.close()
    return df


def engineer_features(df):
    df = df.copy()
    for vt in ["off_palette_color", "non_standard_spacing", "duplicate_component",
               "inconsistent_corner_radius", "unapproved_font_size"]:
        df[f"type_{vt}"] = (df["violation_type"] == vt).astype(int)
    for sev in ["cosmetic", "moderate", "brand_critical"]:
        df[f"sev_{sev}"] = (df["severity"] == sev).astype(int)
    return df


def train():
    df = load_dataframe()
    df = engineer_features(df)

    X = df[FEATURE_COLUMNS]
    y = df["ground_truth_merit"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    rf = RandomForestClassifier(n_estimators=300, max_depth=7, min_samples_leaf=5, random_state=42)
    gb = GradientBoostingClassifier(n_estimators=200, max_depth=3, learning_rate=0.05, random_state=42)
    lr = LogisticRegression(max_iter=1000, random_state=42)

    ensemble = VotingClassifier(
        estimators=[("rf", rf), ("gb", gb), ("lr", lr)],
        voting="soft",
        weights=[2, 2, 1],
    )
    ensemble.fit(X_train_scaled, y_train)

    probs = ensemble.predict_proba(X_test_scaled)[:, 1]
    preds = (probs >= 0.5).astype(int)

    metrics = {
        "roc_auc": round(roc_auc_score(y_test, probs), 4),
        "precision": round(precision_score(y_test, preds), 4),
        "recall": round(recall_score(y_test, preds), 4),
        "f1": round(f1_score(y_test, preds), 4),
        "n_train": len(X_train),
        "n_test": len(X_test),
    }

    rf_only = RandomForestClassifier(n_estimators=300, max_depth=7, min_samples_leaf=5, random_state=42)
    rf_only.fit(X_train_scaled, y_train)
    importances = dict(zip(FEATURE_COLUMNS, rf_only.feature_importances_.tolist()))

    train_means = X_train.mean().to_dict()
    train_stds = X_train.std().replace(0, 1).to_dict()

    artifact = {
        "model": ensemble,
        "scaler": scaler,
        "feature_columns": FEATURE_COLUMNS,
        "feature_importances": importances,
        "train_means": train_means,
        "train_stds": train_stds,
        "metrics": metrics,
    }

    with open(MODEL_PATH, "wb") as f:
        pickle.dump(artifact, f)

    print("Training complete.")
    print(json.dumps(metrics, indent=2))
    print("\nTop feature importances:")
    for feat, imp in sorted(importances.items(), key=lambda x: -x[1])[:6]:
        print(f"  {feat:35s} {imp:.4f}")

    return metrics


if __name__ == "__main__":
    train()
