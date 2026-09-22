"""Train the late-payment prediction model.

Interpretable models only, per spec: logistic regression or random forest.
Uses a temporal train/test split (train on earlier invoices, test on later
ones) rather than a random split, since a random split would leak
future payment-behavior information into training via the per-customer
expanding features.
"""
from __future__ import annotations

from datetime import datetime, timezone

import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.core.config import MODELS_DIR
from app.ml.evaluate import evaluate_model
from app.ml.features import FEATURE_COLUMNS, training_frame

MODEL_PATH = MODELS_DIR / "late_payment_model.joblib"
MIN_TRAINING_ROWS = 20


def _build_pipeline(model_type: str) -> Pipeline:
    if model_type == "logistic_regression":
        estimator = LogisticRegression(max_iter=1000, class_weight="balanced")
    elif model_type == "random_forest":
        estimator = RandomForestClassifier(
            n_estimators=200, max_depth=8, min_samples_leaf=5,
            class_weight="balanced", random_state=42, n_jobs=-1,
        )
    else:
        raise ValueError(f"Unknown model_type: {model_type}")
    return Pipeline([("scaler", StandardScaler()), ("model", estimator)])


def train_late_payment_model(model_type: str = "random_forest") -> dict:
    df = training_frame()
    if len(df) < MIN_TRAINING_ROWS:
        return {
            "trained": False,
            "reason": f"Need at least {MIN_TRAINING_ROWS} paid invoices with known outcomes, "
                      f"found {len(df)}.",
            "rows_available": len(df),
        }

    df = df.sort_values("invoice_date")
    split_idx = int(len(df) * 0.8)
    train_df, test_df = df.iloc[:split_idx], df.iloc[split_idx:]
    if train_df.empty or test_df.empty:
        train_df, test_df = df, df  # too little data to split; evaluate in-sample

    X_train, y_train = train_df[FEATURE_COLUMNS], train_df["label_late"]
    pipeline = _build_pipeline(model_type)
    pipeline.fit(X_train, y_train)

    metrics = evaluate_model(pipeline, test_df[FEATURE_COLUMNS], test_df["label_late"])
    importances = _explainability(pipeline, model_type)

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "pipeline": pipeline,
            "model_type": model_type,
            "feature_columns": FEATURE_COLUMNS,
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "n_train": len(train_df),
            "n_test": len(test_df),
        },
        MODEL_PATH,
    )

    return {
        "trained": True,
        "model_type": model_type,
        "n_train": len(train_df),
        "n_test": len(test_df),
        "metrics": metrics,
        "feature_importance": importances,
    }


def _explainability(pipeline: Pipeline, model_type: str) -> dict[str, float]:
    model = pipeline.named_steps["model"]
    if model_type == "logistic_regression":
        values = model.coef_[0]
    else:
        values = model.feature_importances_
    return {col: round(float(v), 4) for col, v in zip(FEATURE_COLUMNS, values)}
