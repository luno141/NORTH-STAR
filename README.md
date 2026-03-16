# PS13 - Federated Threat Intelligence Integrity

Complete local-first hackathon prototype for:

**"Federated Threat Intelligence Integrity: Collaborative threat-intelligence sharing with integrity, access control, and contributor reputation."**

This repo includes a full stack implementation:
- Frontend: Next.js 14 + Tailwind dashboard
- Backend: FastAPI REST API
- Database: PostgreSQL + pgvector
- Queue/Jobs: Redis + Celery worker
- ML: scikit-learn TF-IDF + LogisticRegression classifier
- Optional 10B+ LLM mode: vLLM + Qwen2.5-14B-Instruct(-AWQ)

## Production Upgrades Implemented

This build now includes the hardening upgrades requested:

- Timezone-safe timestamps (`TIMESTAMPTZ`) with startup schema migration/backfill.
- Source reliability table and weighted credibility scoring.
- Calibrated sklearn probabilities + multi-label prediction output.
- Fuzzy deduplication (canonicalized values + similarity threshold).
- Semantic embedding path with pgvector index + fallback strategy.
- Hashed API keys + JWT session login + key rotation API.
- Ledger HMAC signatures + periodic/manual anchor chain.
- Request ID middleware + Prometheus metrics + readiness probe.
- Integration test suite (`pytest`) for health/auth/ingest/integrity flows.

## 1) Architecture Overview (1-page)

The system is multi-tenant (OrgA/OrgB/OrgC) with API-key based tenant access and RBAC roles (`org_admin`, `analyst`, `contributor`, `viewer`). All intel is normalized into a STIX-like schema and written to `threat_intel`. On every insert, an append-only hash-chained ledger record is written into `ledger_entries` (`prev_hash -> hash`) to make tampering detectable.

Ingestion supports:
- RSS feeds (security advisories)
- Paste/text dump ingestion
- CSV IoC uploads

ML pipeline classifies intel (`leak`, `malware`, `phishing`, `vuln`, `discussion`, `benign`) and computes scores:
- `severity` (0-100)
- `credibility` (0-100)

Credibility and federation visibility are influenced by contributor reputation and analyst feedback (`approve`, `upvote`, `flag false-positive`). Federation hub shares intel between orgs based on policy thresholds (`min_credibility`, `min_reputation`) and source visibility.

`pgvector` stores lightweight embeddings for similarity search and future semantic workflows.

### ASCII Diagram

```text
             +-------------------------------+
             |          Next.js UI           |
             | Feed | Detail | Contrib |Audit|
             +---------------+---------------+
                             |
                             v
+----------------------------+-----------------------------+
|                      FastAPI Backend                     |
|  Auth/RBAC | Ingestion | Scoring | Federation | Ledger   |
+--------+---------------+---------+------------+----------+
         |               |         |            |
         v               v         v            v
   +-----------+   +-----------+  +-----------------------+
   | PostgreSQL|   |  Celery   |  | Redis (broker/result) |
   | + pgvector|<->|  Worker   |<-+-----------------------+
   | intel,log |   | rss/fed   |
   +-----------+   +-----------+
```

## 2) Local Setup (Linux/Debian)

### Prerequisites
- Docker + Docker Compose plugin
- 6GB+ RAM recommended
- For 10B+ LLM mode: NVIDIA GPU (24GB+ VRAM recommended), NVIDIA Container Toolkit, Hugging Face access for model pulls

### Steps
1. Clone/open this repo.
2. Copy env template:
   ```bash
   cp .env.example .env
   ```
3. Build and start all services:
   ```bash
   docker compose up --build
   ```
4. Open:
   - Frontend: http://localhost:3000
   - Backend docs: http://localhost:8000/docs

On first backend startup, database schema + seed data are auto-created.

## 3) Seeded Demo Credentials (API Keys)

Use in header `X-API-Key` for backend calls:
- OrgA admin: `orga_admin_key`
- OrgA analyst: `ana_analyst_key`
- OrgA contributor: `carl_contrib_key`
- OrgA viewer: `vera_viewer_key`
- OrgB admin: `orgb_admin_key`
- OrgC admin: `orgc_admin_key`

Frontend defaults to `NEXT_PUBLIC_DEFAULT_API_KEY=orga_admin_key`.

## 4) API Highlights

- `GET /api/feed`
  - Filters: `org_id`, `indicator_type`, `min_severity`, `min_credibility`, `hours`
- `POST /api/auth/login` (issue JWT from API key)
- `GET /api/auth/whoami`
- `POST /api/auth/rotate-key?scope=user|org`
- `GET /api/intel/{id}`
- `GET /api/intel/{id}/proof` (ledger proof)
- `GET /api/intel/{id}/similar` (pgvector similarity)
- `POST /api/intel`
- `POST /api/ingest/rss`
- `POST /api/ingest/text`
- `POST /api/ingest/csv`
- `POST /api/federation/run`
- `POST /api/integrity/anchor`
- `GET /api/integrity/verify` => `PASS/FAIL + first_broken_index`
- `GET /api/metrics` (Prometheus)
- `GET /api/ready`
- `GET /api/contributors`
- `POST /api/contributors/action`

## 5) ML Workflow

### 5A) Fast baseline (existing sklearn flow)

From backend container shell:

```bash
docker compose exec backend bash
python scripts/generate_dataset.py
python scripts/train.py
python scripts/export_model.py
```

Outputs:
- Dataset: `backend/data/dataset.jsonl`, `backend/data/dataset.csv`
- Pipeline artifact: `backend/artifacts/pipeline.joblib`
- Runtime model bundle: `backend/models/model.joblib`

Classifier metrics are printed from calibrated `classification_report` (precision/recall/F1) plus mean top-confidence.

To apply latest model/scoring logic to existing records:

```bash
docker compose exec backend bash -lc "cd /app && PYTHONPATH=/app python scripts/rescore_existing.py"
```

### 5B) 10B+ LLM mode (new)

This project can run a 14B classifier path using an OpenAI-compatible vLLM service and optional QLoRA fine-tuning.

#### Step 1: Enable LLM inference service

Set in `.env`:

```bash
CLASSIFIER_MODE=llm
LLM_MODEL_NAME=Qwen/Qwen2.5-14B-Instruct-AWQ
LLM_API_BASE=http://llm:8000/v1
LLM_API_KEY=EMPTY
HUGGING_FACE_HUB_TOKEN=<your_hf_token_if_needed>
```

Start stack with LLM profile:

```bash
docker compose --profile llm up --build
```

The LLM service is exposed on host as `http://localhost:8001/v1` and internally as `http://llm:8000/v1`.

#### Step 2: Build a larger online dataset

This pulls large cybersecurity corpora from online sources:
- Malicious URL dataset (`good`/`bad`) from GitHub
- URLhaus recent malware URLs
- NVD CVE descriptions
- Synthetic leak/discussion corpora for label coverage

```bash
docker compose exec backend bash -lc \"cd /app && PYTHONPATH=/app python scripts/build_large_online_dataset.py\"
```

Outputs:
- `backend/data/llm_large_dataset.csv`
- `backend/data/llm_sft_train.jsonl` (chat-format for SFT)

#### Step 3: QLoRA fine-tune a 14B model (Colab recommended)

In Colab/remote GPU environment:

```bash
pip install -r backend/scripts/requirements-llm-train.txt
python backend/scripts/train_qlora_14b.py \
  --model-name Qwen/Qwen2.5-14B-Instruct \
  --train-file backend/data/llm_sft_train.jsonl \
  --output-dir adapters/qwen25-14b-cti-qlora
```

This produces a LoRA adapter directory (`adapters/...`) for 10B+ parameter base model inference.

#### Step 4: Validate backend LLM classifier path

```bash
docker compose exec backend bash -lc \"cd /app && PYTHONPATH=/app python scripts/test_llm_classifier.py\"
```

## 6) Demo Script

See [DEMO_SCRIPT.md](DEMO_SCRIPT.md) for exact click path + talk track.

## 7) Common Errors & Fixes

1. `ModuleNotFoundError: app`
   - Run scripts from `/app` (backend root inside container).
2. `Invalid API key`
   - Add `X-API-Key` header, e.g. `orga_admin_key`.
3. Frontend cannot reach backend
   - Ensure `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000` in `.env`.
4. Integrity verify returns FAIL
   - Ledger was tampered (or schema mismatch). Rebuild DB for clean demo:
     ```bash
     docker compose down -v
     docker compose up --build
     ```
5. RSS ingestion creates 0 rows
   - Some external feeds may be unavailable/rate-limited. Use text/CSV ingest endpoints for deterministic demo.
6. Frontend/backend works but LLM mode falls back silently
   - Check `CLASSIFIER_MODE=llm` and `LLM_API_BASE=http://llm:8000/v1`, then verify `llm` service is running via `docker compose --profile llm ps`.
7. LLM container exits on startup
   - Ensure GPU runtime is configured (`nvidia-smi` works on host) and Docker has NVIDIA Container Toolkit enabled.
8. NVD dataset build is slow
   - Public NVD API is rate-limited; reduce `--vuln` count in `scripts/build_large_online_dataset.py` arguments if needed.

## 8) Useful Commands

```bash
# Start
docker compose up --build

# Ingest real public feeds (OpenPhish + URLhaus + RSS) with one command
docker compose exec backend bash -lc "cd /app && PYTHONPATH=/app python scripts/ingest_real_feeds.py --max-openphish 500 --max-urlhaus 500"

# Run federation manually
curl -X POST http://localhost:8000/api/federation/run -H 'X-API-Key: ana_analyst_key'

# Verify integrity chain
curl http://localhost:8000/api/integrity/verify -H 'X-API-Key: ana_analyst_key'

# Create a ledger anchor snapshot
curl -X POST http://localhost:8000/api/integrity/anchor -H 'X-API-Key: ana_analyst_key'

# JWT login (UI/session flow)
curl -X POST http://localhost:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"api_key":"orga_admin_key"}'

# Run integration tests
docker compose exec backend bash -lc "cd /app && pytest -q"

# Upload sample CSV
curl -X POST http://localhost:8000/api/ingest/csv \
  -H 'X-API-Key: carl_contrib_key' \
  -F 'file=@samples/iocs.csv'
```
# NORTH-STAR
