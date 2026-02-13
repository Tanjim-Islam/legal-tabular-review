from __future__ import annotations

from fastapi.testclient import TestClient

from app import app
from src.settings import EXPORTS_DIR


def test_quick_mode_end_to_end_generates_table_and_exports() -> None:
    client = TestClient(app)

    run_resp = client.post("/runs", json={"mode": "quick", "wait": True})
    assert run_resp.status_code == 200

    job = run_resp.json()["job"]
    assert job["status"] == "COMPLETED"

    table_resp = client.get("/results/table", params={"job_id": job["id"]})
    assert table_resp.status_code == 200

    payload = table_resp.json()
    assert payload["rows"]

    has_citation_with_confidence = False
    for row in payload["rows"]:
        for cell in row["cells"]:
            if cell.get("citation") and (cell.get("confidence") or 0) > 0:
                has_citation_with_confidence = True
                break
        if has_citation_with_confidence:
            break

    assert has_citation_with_confidence

    before_csv = {p.name for p in EXPORTS_DIR.glob("*.csv")}
    before_xlsx = {p.name for p in EXPORTS_DIR.glob("*.xlsx")}

    csv_resp = client.post("/exports/csv", json={"job_id": job["id"]})
    xlsx_resp = client.post("/exports/xlsx", json={"job_id": job["id"]})

    assert csv_resp.status_code == 200
    assert xlsx_resp.status_code == 200

    after_csv = {p.name for p in EXPORTS_DIR.glob("*.csv")}
    after_xlsx = {p.name for p in EXPORTS_DIR.glob("*.xlsx")}

    assert after_csv - before_csv
    assert after_xlsx - before_xlsx
