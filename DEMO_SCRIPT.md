# Demo Script (Exact Click Path + Talk Track)

## 0) Start stack
```bash
cp .env.example .env
docker compose up --build
```

## 1) Open feed
- Go to `http://localhost:3000/feed`
- Talk track:
  - "This is a multi-tenant threat intel feed normalized into a STIX-like schema."
  - "Each record has model-driven severity/credibility and role-aware visibility."

## 2) Show filters
- In filter bar, set:
  - `indicator_type = domain`
  - `min_severity = 60`
  - Click **Apply**
- Talk track:
  - "Analysts can quickly triage by type, severity, credibility, and time window."

## 3) Open intel detail
- Click any Intel ID in table
- Talk track:
  - "Detail view includes evidence, class probabilities, and top TF-IDF explanation terms."
  - "Below, you can see integrity proof entries from the append-only hash chain ledger."

## 4) Contributor reputation actions
- Open `http://localhost:3000/contributors`
- For any contributor row:
  - Enter an Intel ID (from feed)
  - Click **Approve** then **Flag FP**
- Talk track:
  - "Analyst feedback updates contributor reputation from 0-100."
  - "Reputation directly affects credibility and federation visibility defaults."

## 5) Run federation sharing
- Open `http://localhost:3000/feed`
- Click **Run Federation**
- Talk track:
  - "Federation hub applies policy thresholds (credibility + contributor reputation)."
  - "Intel is copied cross-org with provenance (`shared_from_org_id`) and dedupe checks."

## 6) Integrity audit
- Open `http://localhost:3000/audit`
- Click **Run Verify**
- Talk track:
  - "This verifies the entire hash chain in Postgres and returns PASS/FAIL."
  - "If tampered, we get first broken index for forensic pinpointing."

## 7) Optional ingestion API demo
```bash
curl -X POST http://localhost:8000/api/ingest/text \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: carl_contrib_key' \
  -d '{"source":"paste","text":"evil-login-service.com|Credential harvesting infra"}'

curl -X POST http://localhost:8000/api/ingest/csv \
  -H 'X-API-Key: carl_contrib_key' \
  -F 'file=@samples/iocs.csv'
```
- Talk track:
  - "We support RSS, paste/text, and CSV IoC ingest into one normalized schema."
