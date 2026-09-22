"""Model evaluation: accuracy, precision, recall, F1, ROC-AUC on a held-out
set. Kept separate from training so it can also be run standalone against a
freshly loaded model."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def evaluate_model(pipeline, X_test: pd.DataFrame, y_test: pd.Series) -> dict:
    if len(X_test) == 0:
        return {"note": "No test rows available."}

    y_pred = pipeline.predict(X_test)
    proba = pipeline.predict_proba(X_test)[:, 1]

    metrics = {
        "accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
        "precision": round(float(precision_score(y_test, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_test, y_pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_test, y_pred, zero_division=0)), 4),
        "positive_rate_actual": round(float(np.mean(y_test)), 4),
        "positive_rate_predicted": round(float(np.mean(y_pred)), 4),
        "n_test": int(len(y_test)),
    }
    if len(set(y_test)) > 1:
        metrics["roc_auc"] = round(float(roc_auc_score(y_test, proba)), 4)
    else:
        metrics["roc_auc"] = None
        metrics["note"] = "ROC-AUC undefined: test set has only one class."
    return metrics
