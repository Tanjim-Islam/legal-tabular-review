Backend

FastAPI backend for Legal Tabular Review.

Implemented modules:
- `src/api/` routes and request models
- `src/parsers/` PDF/HTML parsing with page/section chunking
- `src/extraction/` deterministic template loader, extractor, normalizers
- `src/services/` inventory, run orchestration, review/audit, exports
- `src/database.py` SQLite schema and access layer
- `src/settings.py` repo/runtime paths

Implemented endpoints:
- `GET /health`
- `GET /projects`
- `GET /documents`
- `POST /documents/upload`
- `POST /runs`
- `GET /jobs/{job_id}`
- `GET /results/table`
- `PATCH /cells/{cell_id}`
- `GET /cells/{cell_id}/audit`
- `POST /exports/csv`
- `POST /exports/xlsx`

Notes:
- Uses local SQLite under `artifacts/`.
- Uses local thread-based async for non-blocking runs.
- No external AI APIs are used.
