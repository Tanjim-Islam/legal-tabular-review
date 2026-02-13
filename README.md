Legal Tabular Review

Local-only legal document comparison system with deterministic extraction.

What this implementation provides:
- Ingests documents from `data/` and optional uploads.
- Parses PDF and HTML while preserving page or section boundaries.
- Extracts fields using deterministic regex templates and rule-based scoring.
- Stores per-cell value + citation + confidence + review state in SQLite.
- Supports manual edits and review actions with audit history.
- Renders side-by-side table review UI in the frontend.
- Exports reviewed results to CSV and XLSX.
- Supports review states: `CONFIRMED`, `REJECTED`, `MANUAL_UPDATED`, `MISSING_DATA`.

Important:
- No external AI APIs are used.
- Active template is `backend/templates/v1_template.json`.

## Final v1 Fields
- `parties_and_entities`
- `effective_date_term`
- `dispute_resolution`
- `breach_liability`
- `payment_delivery_terms`

Notes:
- `effective_date_term` is extracted as a combined value under one key.
- Citation includes document + location, snippet, and char offsets.

## Project Structure
- `backend/` FastAPI API, parsing/extraction pipeline, SQLite persistence, exports, tests.
- `frontend/` React table-review UI.
- `data/` sample legal documents.
- `artifacts/` generated DB, exports, uploads (ignored by git).

## Setup

### 1) Python environment
From repo root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements-dev.txt
```

### 2) Frontend dependencies

```bash
cd frontend
npm install
cd ..
```

## Run the backend

```bash
source .venv/bin/activate
uvicorn backend.app:app --reload
```

Backend URL: `http://127.0.0.1:8000`

## Run the frontend

```bash
cd frontend
npm run dev
```

Frontend URL: `http://127.0.0.1:5173`

## API Quick Reference
- `GET /health`
- `GET /projects`
- `GET /documents`
- `POST /documents/upload`
- `POST /runs` (`mode=quick|full`, `wait=true|false`)
- `GET /jobs/{job_id}`
- `GET /results/table?job_id=...`
- `PATCH /cells/{cell_id}`
- `GET /cells/{cell_id}/audit`
- `POST /exports/csv`
- `POST /exports/xlsx`

## Quick Mode
Quick mode runs a fast vertical slice:
- first document only
- first 3 PDF pages
- first 5 template fields

Example:

```bash
curl -sS -X POST http://127.0.0.1:8000/runs \
  -H "Content-Type: application/json" \
  -d '{"mode":"quick","wait":true}'
```

## Full Mode
Full mode runs:
- all supported docs in `data/` + uploads
- all pages
- all fields in the active template

Example:

```bash
curl -sS -X POST http://127.0.0.1:8000/runs \
  -H "Content-Type: application/json" \
  -d '{"mode":"full","wait":true}'
```

## Tests and Verification Workflow
Run in this order:

1. Quick smoke test
```bash
cd backend
source ../.venv/bin/activate
python scripts/quick_smoke.py
```

2. Pytest
```bash
cd backend
source ../.venv/bin/activate
pytest
```

3. Frontend build
```bash
cd frontend
npm run build
```

4. Full mode run
```bash
cd backend
source ../.venv/bin/activate
python - <<'PY'
from fastapi.testclient import TestClient
from app import app
client = TestClient(app)
print(client.post('/runs', json={'mode':'full', 'wait':True}).json())
PY
```

## Notes on Citation and Confidence
- Citation stores:
  - document identifier
  - page or section location
  - snippet
  - char offsets (when available)
  - coordinates placeholder (`null` currently)
- Confidence is deterministic and includes explicit reason codes.
- Multiple matches reduce confidence.
