from __future__ import annotations

from pathlib import Path
import sys

from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import app  # noqa: E402
from src.settings import EXPORTS_DIR  # noqa: E402


def fail(message: str) -> None:
    print(f"SMOKE_FAIL: {message}")
    raise SystemExit(1)


def main() -> None:
    client = TestClient(app)

    run_response = client.post("/runs", json={"mode": "quick", "wait": True})
    if run_response.status_code != 200:
        fail(f"quick run request failed ({run_response.status_code})")

    job = run_response.json().get("job", {})
    if job.get("status") != "COMPLETED":
        fail(f"quick run did not complete: {job}")

    table_response = client.get("/results/table", params={"job_id": job["id"]})
    if table_response.status_code != 200:
        fail("table payload endpoint failed")

    table = table_response.json()
    rows = table.get("rows", [])
    if not rows:
        fail("table rows are empty")

    found_supported_cell = False
    for row in rows:
        for cell in row.get("cells", []):
            if cell.get("citation") and (cell.get("confidence") or 0) > 0:
                found_supported_cell = True
                break
        if found_supported_cell:
            break

    if not found_supported_cell:
        fail("no cell had both citation and non-zero confidence")

    before_csv = {p.name for p in EXPORTS_DIR.glob("*.csv")}
    before_xlsx = {p.name for p in EXPORTS_DIR.glob("*.xlsx")}

    csv_response = client.post("/exports/csv", json={"job_id": job["id"]})
    xlsx_response = client.post("/exports/xlsx", json={"job_id": job["id"]})

    if csv_response.status_code != 200:
        fail("CSV export failed")
    if xlsx_response.status_code != 200:
        fail("XLSX export failed")

    after_csv = {p.name for p in EXPORTS_DIR.glob("*.csv")}
    after_xlsx = {p.name for p in EXPORTS_DIR.glob("*.xlsx")}

    if not (after_csv - before_csv):
        fail("no new CSV artifact detected")
    if not (after_xlsx - before_xlsx):
        fail("no new XLSX artifact detected")

    print("SMOKE_OK")


if __name__ == "__main__":
    main()
