from __future__ import annotations

import inspect
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split


def _build_calibrator(base: LogisticRegression):
    sig = inspect.signature(CalibratedClassifierCV.__init__).parameters
    if "estimator" in sig:
        return CalibratedClassifierCV(estimator=base, method="sigmoid", cv="prefit")
    return CalibratedClassifierCV(base_estimator=base, method="sigmoid", cv="prefit")


def main() -> None:
    dataset_path = Path("data/dataset.csv")
    if not dataset_path.exists():
        raise SystemExit("Dataset missing. Run scripts/generate_dataset.py first.")

    df = pd.read_csv(dataset_path)
    x_train_all, x_test, y_train_all, y_test = train_test_split(
        df["text"],
        df["label"],
        test_size=0.2,
        random_state=42,
        stratify=df["label"],
    )
    x_train_fit, x_calib, y_train_fit, y_calib = train_test_split(
        x_train_all,
        y_train_all,
        test_size=0.2,
        random_state=42,
        stratify=y_train_all,
    )

    vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=15000)
    x_fit_vec = vectorizer.fit_transform(x_train_fit)
    x_calib_vec = vectorizer.transform(x_calib)
    x_test_vec = vectorizer.transform(x_test)

    base_model = LogisticRegression(
        max_iter=1500,
        class_weight="balanced",
        solver="lbfgs",
    )
    base_model.fit(x_fit_vec, y_train_fit)

    calibrator = _build_calibrator(base_model)
    calibrator.fit(x_calib_vec, y_calib)

    preds = calibrator.predict(x_test_vec)
    probs = calibrator.predict_proba(x_test_vec)

    report = classification_report(y_test, preds, digits=4)
    print("=== Classification Report (Calibrated) ===")
    print(report)

    # Mean confidence sanity metric.
    top_prob = probs.max(axis=1)
    print(f"Mean top-class confidence: {float(np.mean(top_prob)):.4f}")

    out_dir = Path("artifacts")
    out_dir.mkdir(exist_ok=True)
    model_path = out_dir / "pipeline.joblib"

    import joblib

    joblib.dump(
        {
            "vectorizer": vectorizer,
            "model": calibrator,
            "explainer_model": base_model,
            "classes": list(calibrator.classes_),
        },
        model_path,
    )
    print(f"Saved pipeline to {model_path}")


if __name__ == "__main__":
    main()
