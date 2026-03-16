import csv
import json
import random
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.migrations import run_schema_migrations
from app.db.session import SessionLocal, engine
from app.models.models import Base, ThreatIntel
from app.seed.seed_data import seed_all


LABELS = ["leak", "malware", "phishing", "vuln", "discussion", "benign"]

SYNTHETIC = {
    "phishing": [
        "urgent payroll verification link",
        "mfa reset email from fake helpdesk",
        "credential harvesting domain observed",
    ],
    "malware": [
        "trojan loader hash beaconing to c2",
        "ransomware binary dropped by macro",
        "suspicious powershell payload execution",
    ],
    "vuln": [
        "critical cve with remote code execution",
        "patch bypass discovered in vpn service",
        "public exploit released for auth flaw",
    ],
    "leak": [
        "database dump posted on paste site",
        "api keys leaked in public repository",
        "internal document exposure via misconfig",
    ],
    "discussion": [
        "research forum discussing exploit reliability",
        "thread debating malware attribution claims",
        "analyst note about weak signal rumor",
    ],
    "benign": [
        "security awareness newsletter announcement",
        "false alarm caused by scanner misfire",
        "routine maintenance notice from vendor",
    ],
}


def infer_label(row: ThreatIntel) -> str:
    if row.classification in LABELS:
        return row.classification
    text = f"{row.context_text} {row.evidence}".lower()
    if "phish" in text or "credential" in text:
        return "phishing"
    if "malware" in text or "ransom" in text or "trojan" in text:
        return "malware"
    if "cve" in text or "vuln" in text or "exploit" in text:
        return "vuln"
    if "leak" in text or "dump" in text or "exfil" in text:
        return "leak"
    if "false" in text or "benign" in text:
        return "benign"
    return "discussion"


def ensure_db_ready() -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=engine)

    db: Session = SessionLocal()
    try:
        run_schema_migrations(db)
        seed_all(db)
    finally:
        db.close()


def main() -> None:
    out_dir = Path("data")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_jsonl = out_dir / "dataset.jsonl"
    out_csv = out_dir / "dataset.csv"

    ensure_db_ready()

    db: Session = SessionLocal()
    try:
        rows = db.query(ThreatIntel).limit(1500).all()
    finally:
        db.close()

    dataset = []
    for row in rows:
        text = f"{row.value} {row.context_text} {row.evidence}"
        dataset.append({"text": text, "label": infer_label(row), "source": "ingested"})

    random.seed(42)
    for label, phrases in SYNTHETIC.items():
        for _ in range(140):
            text = random.choice(phrases)
            text += f" {random.choice(['urgent', 'observed', 'reported', 'confirmed'])}"
            dataset.append({"text": text, "label": label, "source": "synthetic"})

    random.shuffle(dataset)

    with out_jsonl.open("w", encoding="utf-8") as f:
        for row in dataset:
            f.write(json.dumps(row) + "\n")

    with out_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["text", "label", "source"])
        writer.writeheader()
        writer.writerows(dataset)

    print(f"Wrote {len(dataset)} rows to {out_jsonl} and {out_csv}")


if __name__ == "__main__":
    main()
