from pathlib import Path

import joblib


def main() -> None:
    pipeline_path = Path("artifacts/pipeline.joblib")
    if not pipeline_path.exists():
        raise SystemExit("Missing artifacts/pipeline.joblib. Run scripts/train.py first.")

    pipeline = joblib.load(pipeline_path)
    vectorizer = pipeline["vectorizer"]
    calibrated_model = pipeline["model"]
    explainer_model = pipeline.get("explainer_model")

    bundle = {
        "vectorizer": vectorizer,
        "calibrated_model": calibrated_model,
        "explainer_model": explainer_model,
        "classes": pipeline.get("classes", []),
    }

    out_path = Path("models/model.joblib")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, out_path)
    print(f"Exported bundle to {out_path}")


if __name__ == "__main__":
    main()
