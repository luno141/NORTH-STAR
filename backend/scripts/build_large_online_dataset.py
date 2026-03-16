from __future__ import annotations

import argparse
import csv
import io
import json
import random
import time
from pathlib import Path

import pandas as pd
import requests


MALICIOUS_URL_DATASET = (
    "https://raw.githubusercontent.com/faizann24/"
    "Using-machine-learning-to-detect-malicious-URLs/master/data/data.csv"
)
URLHAUS_RECENT_CSV = "https://urlhaus.abuse.ch/downloads/csv_recent/"
NVD_API = "https://services.nvd.nist.gov/rest/json/cves/2.0"

LABELS = ["leak", "malware", "phishing", "vuln", "discussion", "benign"]


def fetch_url_binary_dataset(max_benign: int, max_phishing: int, seed: int) -> pd.DataFrame:
    df = pd.read_csv(MALICIOUS_URL_DATASET)
    df = df.rename(columns={"url": "text", "label": "source_label"})
    df["source_label"] = df["source_label"].astype(str).str.strip().str.lower()

    benign = df[df["source_label"] == "good"]["text"].dropna().drop_duplicates().sample(
        min(max_benign, int((df["source_label"] == "good").sum())), random_state=seed
    )
    phishing = df[df["source_label"] == "bad"]["text"].dropna().drop_duplicates().sample(
        min(max_phishing, int((df["source_label"] == "bad").sum())), random_state=seed
    )

    d1 = pd.DataFrame({"text": benign.values, "label": "benign", "source": "online:malicious-url-good"})
    d2 = pd.DataFrame({"text": phishing.values, "label": "phishing", "source": "online:malicious-url-bad"})
    return pd.concat([d1, d2], ignore_index=True)


def fetch_urlhaus_malware(max_rows: int) -> pd.DataFrame:
    resp = requests.get(URLHAUS_RECENT_CSV, timeout=60)
    resp.raise_for_status()

    rows: list[dict[str, str]] = []
    filtered = "\n".join([line for line in resp.text.splitlines() if line and not line.startswith("#")])
    reader = csv.reader(io.StringIO(filtered))
    for row in reader:
        if len(row) < 3:
            continue
        url = row[2].strip()
        threat = row[5].strip().lower() if len(row) > 5 else "malware"
        if not url:
            continue
        rows.append(
            {
                "text": f"{threat} url {url}",
                "label": "malware",
                "source": "online:urlhaus",
            }
        )
        if len(rows) >= max_rows:
            break

    return pd.DataFrame(rows)


def fetch_nvd_vuln(max_rows: int, page_size: int = 2000) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    start_index = 0

    while len(rows) < max_rows:
        params = {"resultsPerPage": page_size, "startIndex": start_index}
        resp = requests.get(NVD_API, params=params, timeout=90)
        resp.raise_for_status()
        payload = resp.json()
        vulns = payload.get("vulnerabilities", [])
        if not vulns:
            break

        for item in vulns:
            cve = item.get("cve", {})
            cve_id = cve.get("id", "")
            desc = ""
            for d in cve.get("descriptions", []):
                if d.get("lang") == "en":
                    desc = d.get("value", "")
                    break
            if not desc:
                continue
            text = f"{cve_id}. {desc}".strip()
            rows.append({"text": text, "label": "vuln", "source": "online:nvd"})
            if len(rows) >= max_rows:
                break

        start_index += page_size
        # Respect public API rate limiting.
        time.sleep(6)

    return pd.DataFrame(rows)


def synthetic_samples(label: str, count: int, seed: int) -> pd.DataFrame:
    random.seed(seed)
    if label == "leak":
        templates = [
            "credentials dump posted in public channel containing {asset}",
            "possible data breach exposed {asset} from {system}",
            "s3 bucket leak includes {asset} and internal records",
            "api keys leaked in repository for {system}",
        ]
        assets = ["customer emails", "access tokens", "password hashes", "source code"]
        systems = ["crm portal", "billing stack", "vpn gateway", "hr platform"]
        texts = [random.choice(templates).format(asset=random.choice(assets), system=random.choice(systems)) for _ in range(count)]
    else:
        templates = [
            "security forum discussion about {topic} with low confidence",
            "analyst conversation debating attribution for {topic}",
            "community post discussing exploit rumors around {topic}",
            "open-source thread about potential incident tied to {topic}",
        ]
        topics = ["ransomware affiliate", "zero-day exploit", "credential stuffing", "supply chain attack"]
        texts = [random.choice(templates).format(topic=random.choice(topics)) for _ in range(count)]

    return pd.DataFrame({"text": texts, "label": label, "source": f"synthetic:{label}"})


def to_sft_jsonl(df: pd.DataFrame, out_file: Path) -> None:
    system = (
        "You are a threat-intel classifier. "
        "Classify text as one of: leak, malware, phishing, vuln, discussion, benign. "
        "Respond with JSON: {\"label\": \"...\"}."
    )
    out_file.parent.mkdir(parents=True, exist_ok=True)

    with out_file.open("w", encoding="utf-8") as f:
        for _, row in df.iterrows():
            obj = {
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": f"Classify this intel text:\n{row['text']}"},
                    {"role": "assistant", "content": f"{{\"label\": \"{row['label']}\"}}"},
                ]
            }
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build large online dataset for 10B+ LLM fine-tuning")
    parser.add_argument("--out-csv", default="data/llm_large_dataset.csv")
    parser.add_argument("--out-jsonl", default="data/llm_sft_train.jsonl")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--benign", type=int, default=120000)
    parser.add_argument("--phishing", type=int, default=120000)
    parser.add_argument("--malware", type=int, default=60000)
    parser.add_argument("--vuln", type=int, default=30000)
    parser.add_argument("--leak", type=int, default=25000)
    parser.add_argument("--discussion", type=int, default=25000)
    args = parser.parse_args()

    print("Downloading large benign/phishing URL corpus...")
    url_df = fetch_url_binary_dataset(max_benign=args.benign, max_phishing=args.phishing, seed=args.seed)

    print("Downloading malware URL corpus (URLhaus)...")
    malware_df = fetch_urlhaus_malware(max_rows=args.malware)

    print("Downloading NVD vulnerability corpus...")
    vuln_df = fetch_nvd_vuln(max_rows=args.vuln)

    print("Generating leak/discussion synthetic corpora...")
    leak_df = synthetic_samples("leak", args.leak, args.seed)
    disc_df = synthetic_samples("discussion", args.discussion, args.seed + 1)

    df = pd.concat([url_df, malware_df, vuln_df, leak_df, disc_df], ignore_index=True)
    df["text"] = df["text"].astype(str).str.strip()
    df = df[df["text"].str.len() > 4]
    df = df[df["label"].isin(LABELS)]
    df = df.drop_duplicates(subset=["text", "label"]).sample(frac=1.0, random_state=args.seed)

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_csv, index=False)

    out_jsonl = Path(args.out_jsonl)
    to_sft_jsonl(df[["text", "label"]], out_jsonl)

    print("\nSaved dataset files:")
    print(f"- {out_csv} ({len(df)} rows)")
    print(f"- {out_jsonl}")
    print("\nLabel distribution:")
    print(df["label"].value_counts())


if __name__ == "__main__":
    main()
