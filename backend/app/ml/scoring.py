from __future__ import annotations

import hashlib
import json
import os
import re
from functools import lru_cache
from typing import Any

import joblib
import numpy as np
import requests

from app.core.config import settings


LABELS = ["leak", "malware", "phishing", "vuln", "discussion", "benign"]

SEVERITY_PRIOR = {
    "leak": 85,
    "malware": 90,
    "phishing": 75,
    "vuln": 70,
    "discussion": 40,
    "benign": 15,
}

RULE_KEYWORDS = {
    "malware": [
        "malware",
        "trojan",
        "ransom",
        "botnet",
        "c2",
        "dropper",
        "payload",
        "mirai",
        "mozi",
        "urlhaus",
        "malware_download",
        "elf",
    ],
    "phishing": [
        "phish",
        "credential",
        "verify",
        "login",
        "mfa",
        "openphish",
        "spoof",
        "harvest",
    ],
    "vuln": [
        "cve-",
        "vuln",
        "vulnerability",
        "rce",
        "exploit",
        "patch bypass",
    ],
    "leak": [
        "leak",
        "dump",
        "breach",
        "exfil",
        "paste",
        "stolen",
    ],
    "benign": [
        "newsletter",
        "maintenance",
        "training",
        "false alarm",
        "benign",
    ],
}

HIGH_RISK_TAGS = {
    "ransomware",
    "malware",
    "trojan",
    "c2",
    "botnet",
    "phishing",
    "credential",
    "leak",
    "exfil",
    "rce",
    "exploit",
}

SUSPICIOUS_URL_TOKENS = {
    "bin.sh",
    "login",
    "verify",
    "reset",
    "update",
    ".php",
    "/i",
    ".xml",
}

INDICATOR_RISK = {
    "cve": 12.0,
    "hash": 11.0,
    "ip": 9.0,
    "url": 8.0,
    "email": 8.0,
    "domain": 7.0,
    "text": 5.0,
}

_model_cache: dict[str, Any] = {}


def _default_probs() -> dict[str, float]:
    low = {label: 0.05 for label in LABELS}
    low["discussion"] = 0.55
    low["benign"] = 0.20
    return low


def _normalize_probs(prob_map: dict[str, float]) -> dict[str, float]:
    normalized = {label: max(float(prob_map.get(label, 0.0)), 0.0) for label in LABELS}
    total = sum(normalized.values())
    if total <= 0:
        return _default_probs()
    return {k: v / total for k, v in normalized.items()}


def _heuristic_terms(text: str, top_k: int = 8) -> list[str]:
    stop = {
        "the",
        "and",
        "this",
        "that",
        "with",
        "from",
        "have",
        "been",
        "into",
        "your",
        "for",
        "http",
        "https",
    }
    words = re.findall(r"[a-zA-Z0-9_.-]{4,}", text.lower())
    seen: list[str] = []
    for word in words:
        if word in stop:
            continue
        if word not in seen:
            seen.append(word)
        if len(seen) >= top_k:
            break
    return seen


def _extract_json(content: str) -> dict[str, Any]:
    try:
        return json.loads(content)
    except Exception:
        pass

    match = re.search(r"\{.*\}", content, flags=re.S)
    if not match:
        raise ValueError("LLM response did not contain JSON")
    return json.loads(match.group(0))


def _rule_hits(label: str, text: str) -> int:
    return sum(1 for token in RULE_KEYWORDS.get(label, []) if token in text)


def _rule_terms(text: str, top_k: int = 4) -> list[str]:
    found: list[str] = []
    for keywords in RULE_KEYWORDS.values():
        for token in keywords:
            if token in text and token not in found:
                found.append(token)
                if len(found) >= top_k:
                    return found
    return found


def _merge_terms(base: list[str], extra: list[str], top_k: int = 8) -> list[str]:
    merged: list[str] = []
    for term in [*base, *extra]:
        token = str(term).strip().lower()
        if not token:
            continue
        if token in merged:
            continue
        merged.append(token)
        if len(merged) >= top_k:
            break
    return merged


def _apply_rule_boosts(prob_map: dict[str, float], text: str) -> dict[str, float]:
    boosted = dict(prob_map)
    threat_hits = 0

    for label in ("malware", "phishing", "vuln", "leak"):
        hits = _rule_hits(label, text)
        if hits:
            boosted[label] = boosted.get(label, 0.0) + 0.18 * hits
            threat_hits += hits

    benign_hits = _rule_hits("benign", text)
    if benign_hits:
        boosted["benign"] = boosted.get("benign", 0.0) + 0.10 * benign_hits
        boosted["discussion"] = boosted.get("discussion", 0.0) + 0.04 * benign_hits

    if threat_hits:
        boosted["discussion"] = boosted.get("discussion", 0.0) * 0.65
        boosted["benign"] = boosted.get("benign", 0.0) * 0.75

    return _normalize_probs(boosted)


def _derive_multi_labels(prob_map: dict[str, float], min_prob: float = 0.22, max_labels: int = 3) -> list[str]:
    ranked = sorted(prob_map.items(), key=lambda x: x[1], reverse=True)
    labels = [label for label, prob in ranked if prob >= min_prob][:max_labels]
    if not labels:
        labels = [ranked[0][0]]
    return labels


def _model_confidence(prob_map: dict[str, float]) -> float:
    top = max(prob_map.values()) if prob_map else 0.0
    entropy = -sum(v * np.log(max(v, 1e-12)) for v in prob_map.values())
    norm_entropy = entropy / np.log(len(LABELS))
    confidence = (top * 0.75 + (1 - norm_entropy) * 0.25) * 100
    return float(max(0.0, min(100.0, round(confidence, 2))))


def _call_llm_classifier(text: str) -> tuple[str, list[str], dict[str, float], list[str], float]:
    system_prompt = (
        "You are a cyber threat-intel classifier.\n"
        "Return strict JSON with keys: label, probs, terms.\n"
        "label must be one of: leak, malware, phishing, vuln, discussion, benign.\n"
        "probs must include all 6 labels with numeric probabilities that sum to 1.\n"
        "terms must be a short list of important terms from input text."
    )
    user_prompt = (
        "Classify this threat-intelligence snippet and produce JSON only.\n\n"
        f"TEXT:\n{text}\n"
    )
    headers = {"Content-Type": "application/json"}
    if settings.llm_api_key:
        headers["Authorization"] = f"Bearer {settings.llm_api_key}"
    payload = {
        "model": settings.llm_model_name,
        "temperature": 0,
        "max_tokens": 240,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    resp = requests.post(
        f"{settings.llm_api_base.rstrip('/')}/chat/completions",
        headers=headers,
        json=payload,
        timeout=settings.llm_timeout_seconds,
    )
    resp.raise_for_status()
    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    parsed = _extract_json(content)

    text_lower = text.lower()
    probs = _normalize_probs(parsed.get("probs", {}))
    probs = _apply_rule_boosts(probs, text_lower)

    terms = parsed.get("terms", [])
    if not isinstance(terms, list):
        terms = []
    terms = [str(t) for t in terms if str(t).strip()][:8]
    terms = _merge_terms(terms, _rule_terms(text_lower))
    if not terms:
        terms = _heuristic_terms(text)

    labels = _derive_multi_labels(probs)
    pred_label = labels[0]
    conf = _model_confidence(probs)
    return pred_label, labels, probs, terms, conf


def load_bundle() -> dict[str, Any] | None:
    path = settings.model_path
    if path in _model_cache:
        return _model_cache[path]
    if not os.path.exists(path):
        return None
    bundle = joblib.load(path)
    _model_cache[path] = bundle
    return bundle


def _prob_model(bundle: dict[str, Any]) -> Any:
    if "calibrated_model" in bundle:
        return bundle["calibrated_model"]
    if "model" in bundle:
        return bundle["model"]
    return None


def _explainer_model(bundle: dict[str, Any]) -> Any:
    if "explainer_model" in bundle:
        return bundle["explainer_model"]
    if "model" in bundle:
        return bundle["model"]
    return None


@lru_cache(maxsize=1)
def _get_sentence_model() -> Any | None:
    if settings.embedding_mode.lower() != "semantic":
        return None
    try:
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(settings.embedding_model_name)
    except Exception:
        return None


@lru_cache(maxsize=16)
def _projection_matrix(in_dim: int, out_dim: int) -> np.ndarray:
    seed = (in_dim * 1315423911 + out_dim * 2654435761) % (2**32)
    rng = np.random.default_rng(seed)
    mat = rng.standard_normal((in_dim, out_dim)).astype(np.float32)
    mat /= np.sqrt(out_dim)
    return mat


def _semantic_from_vectorizer(text: str, out_dim: int = 384) -> list[float] | None:
    bundle = load_bundle()
    if not bundle or "vectorizer" not in bundle:
        return None
    vectorizer = bundle["vectorizer"]
    try:
        vec = vectorizer.transform([text]).toarray()[0].astype(np.float32)
        if vec.size == 0:
            return None
        proj = _projection_matrix(vec.size, out_dim)
        dense = vec @ proj
        norm = np.linalg.norm(dense)
        if norm > 0:
            dense = dense / norm
        return dense.astype(float).tolist()
    except Exception:
        return None


def _semantic_from_hash(text: str, out_dim: int = 384) -> list[float]:
    vec = np.zeros(out_dim, dtype=float)
    tokens = re.findall(r"[a-zA-Z0-9_.-]{2,}", text.lower())
    for token in tokens:
        h = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16)
        idx = h % out_dim
        sign = 1 if (h >> 8) % 2 == 0 else -1
        vec[idx] += sign
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec.tolist()


def semantic_embedding(text: str) -> list[float] | None:
    if settings.embedding_mode.lower() != "semantic":
        return None

    model = _get_sentence_model()
    if model is not None:
        try:
            vec = model.encode(text, normalize_embeddings=True)
            arr = np.asarray(vec, dtype=float)
            if arr.ndim > 1:
                arr = arr[0]
            return arr.tolist()
        except Exception:
            pass

    sem = _semantic_from_vectorizer(text, out_dim=384)
    if sem is not None:
        return sem
    return _semantic_from_hash(text, out_dim=384)


def _compress_to_legacy(vec: list[float], dims: int = 32) -> list[float]:
    arr = np.asarray(vec, dtype=float)
    if arr.size == 0:
        return np.zeros(dims, dtype=float).tolist()
    buckets = np.array_split(arr, dims)
    compressed = np.asarray([float(np.mean(b)) for b in buckets], dtype=float)
    norm = np.linalg.norm(compressed)
    if norm > 0:
        compressed = compressed / norm
    return compressed.tolist()


def _hash_embedding(text: str, dims: int = 32) -> list[float]:
    vec = np.zeros(dims, dtype=float)
    tokens = text.lower().split()
    if not tokens:
        return vec.tolist()
    for token in tokens:
        h = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16)
        idx = h % dims
        sign = 1 if (h >> 8) % 2 == 0 else -1
        vec[idx] += sign
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec.astype(float).tolist()


def text_embedding(text: str, dims: int = 32) -> list[float]:
    sem = semantic_embedding(text)
    if sem:
        return _compress_to_legacy(sem, dims=dims)
    return _hash_embedding(text, dims=dims)


def explain_terms(bundle: dict[str, Any], text: str, top_k: int = 8) -> list[str]:
    vectorizer = bundle["vectorizer"]
    model = _explainer_model(bundle)
    if model is None:
        return []

    X = vectorizer.transform([text])
    if not hasattr(model, "coef_"):
        return []

    probs = model.predict_proba(X)[0]
    class_idx = int(np.argmax(probs))
    coefs = model.coef_[class_idx]
    feature_names = vectorizer.get_feature_names_out()
    row = X.toarray()[0]
    scores = row * coefs
    top_indices = np.argsort(scores)[::-1]

    terms: list[str] = []
    for idx in top_indices:
        if row[idx] <= 0:
            continue
        terms.append(feature_names[idx])
        if len(terms) >= top_k:
            break
    return terms


def predict_label_probs(text: str) -> tuple[str, list[str], dict[str, float], list[str], float]:
    text_lower = text.lower()
    if settings.classifier_mode.lower() == "llm":
        try:
            return _call_llm_classifier(text)
        except Exception:
            # Fall through to sklearn/heuristic mode for resilience.
            pass

    bundle = load_bundle()
    if bundle is None:
        probs = _apply_rule_boosts(_default_probs(), text_lower)
        labels = _derive_multi_labels(probs)
        terms = _merge_terms(_heuristic_terms(text), _rule_terms(text_lower))
        return labels[0], labels, probs, terms, _model_confidence(probs)

    vectorizer = bundle["vectorizer"]
    model = _prob_model(bundle)
    if model is None:
        probs = _apply_rule_boosts(_default_probs(), text_lower)
        labels = _derive_multi_labels(probs)
        terms = _merge_terms(_heuristic_terms(text), _rule_terms(text_lower))
        return labels[0], labels, probs, terms, _model_confidence(probs)

    X = vectorizer.transform([text])
    raw_probs = model.predict_proba(X)[0]
    classes = list(getattr(model, "classes_", LABELS))
    prob_map = {label: float(raw_probs[i]) for i, label in enumerate(classes)}
    for label in LABELS:
        prob_map.setdefault(label, 0.0)
    prob_map = _normalize_probs(prob_map)
    prob_map = _apply_rule_boosts(prob_map, text_lower)

    terms = explain_terms(bundle, text)
    terms = _merge_terms(terms, _rule_terms(text_lower))
    if not terms:
        terms = _heuristic_terms(text)

    labels = _derive_multi_labels(prob_map)
    return labels[0], labels, prob_map, terms, _model_confidence(prob_map)


def _content_bonus(
    indicator_type: str,
    value: str,
    tags: list[str],
    context_text: str,
    evidence: str,
) -> tuple[float, float]:
    indicator = (indicator_type or "text").lower().strip()
    base = INDICATOR_RISK.get(indicator, 5.0)
    full_text = f"{value} {context_text} {evidence} {' '.join(tags)}".lower()

    threat_hits = (
        _rule_hits("malware", full_text)
        + _rule_hits("phishing", full_text)
        + _rule_hits("vuln", full_text)
        + _rule_hits("leak", full_text)
    )

    tag_hits = 0
    for tag in tags:
        token = tag.lower().strip()
        if token in HIGH_RISK_TAGS:
            tag_hits += 1

    url_hits = 0
    if indicator == "url":
        for token in SUSPICIOUS_URL_TOKENS:
            if token in value.lower():
                url_hits += 1
        if re.search(r"https?://\d{1,3}(?:\.\d{1,3}){3}", value.lower()):
            url_hits += 2

    cve_hits = 1 if value.lower().startswith("cve-") else 0

    severity_bonus = base + min(12.0, threat_hits * 1.4 + tag_hits * 1.2 + url_hits * 1.3 + cve_hits * 5.0)
    credibility_bonus = min(9.0, threat_hits * 0.8 + tag_hits * 0.7 + url_hits * 0.7 + cve_hits * 2.0)
    return severity_bonus, credibility_bonus


def _fingerprint_offset(value: str) -> float:
    if not value:
        return 0.0
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    frac = int.from_bytes(digest[:2], byteorder="big", signed=False) / 65535.0
    return (frac - 0.5) * 4.0  # -2.0 .. +2.0 deterministic spread


def compute_scores(
    prob_map: dict[str, float],
    labels: list[str],
    model_confidence: float,
    base_confidence: float,
    contributor_reputation: float,
    source_reliability: float,
    source_weight: float,
    source: str,
    indicator_type: str = "text",
    value: str = "",
    tags: list[str] | None = None,
    context_text: str = "",
    evidence: str = "",
) -> tuple[float, float]:
    tags = tags or []
    prob_map = _normalize_probs(prob_map)
    predicted_label = labels[0] if labels else max(prob_map.items(), key=lambda x: x[1])[0]
    label_strength = prob_map[predicted_label] * 100.0

    content_sev_bonus, content_cred_bonus = _content_bonus(
        indicator_type=indicator_type,
        value=value,
        tags=tags,
        context_text=context_text,
        evidence=evidence,
    )
    variance = _fingerprint_offset(value)
    source_reliability = max(0.0, min(100.0, float(source_reliability)))
    source_weight = max(0.1, min(2.0, float(source_weight)))

    multi_label_bonus = max(0.0, min(4.0, (len(labels) - 1) * 1.5))

    severity = (
        SEVERITY_PRIOR.get(predicted_label, 50) * 0.38
        + label_strength * 0.20
        + model_confidence * 0.10
        + base_confidence * 0.14
        + source_reliability * 0.10 * source_weight
        + content_sev_bonus * 0.09
        + multi_label_bonus
        + variance
    )

    credibility = (
        base_confidence * 0.28
        + contributor_reputation * 0.22
        + model_confidence * 0.20
        + label_strength * 0.10
        + source_reliability * 0.16 * source_weight
        + content_cred_bonus * 0.04
        + (variance * 0.5)
    )

    severity = float(max(0, min(100, round(severity, 2))))
    credibility = float(max(0, min(100, round(credibility, 2))))
    return severity, credibility
