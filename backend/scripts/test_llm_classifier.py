from app.ml.scoring import predict_label_probs


if __name__ == "__main__":
    sample = (
        "CVE-2026-12345 remote code execution in edge gateway with active exploitation "
        "observed by SOC telemetry"
    )
    label, labels, probs, terms, confidence = predict_label_probs(sample)
    print("label:", label)
    print("labels:", labels)
    print("model_confidence:", confidence)
    print("probs:", probs)
    print("terms:", terms)
