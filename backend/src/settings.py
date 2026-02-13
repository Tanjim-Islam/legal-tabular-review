from __future__ import annotations

from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SRC_DIR.parent
REPO_ROOT = BACKEND_DIR.parent

DATA_DIR = REPO_ROOT / "data"
ARTIFACTS_DIR = REPO_ROOT / "artifacts"
UPLOADS_DIR = ARTIFACTS_DIR / "uploads"
EXPORTS_DIR = ARTIFACTS_DIR / "exports"
REPORTS_DIR = ARTIFACTS_DIR / "reports"
DB_PATH = ARTIFACTS_DIR / "legal_tabular_review.db"
DEFAULT_TEMPLATE_PATH = BACKEND_DIR / "templates" / "v1_template.json"


def ensure_runtime_dirs() -> None:
    for directory in (ARTIFACTS_DIR, UPLOADS_DIR, EXPORTS_DIR, REPORTS_DIR):
        directory.mkdir(parents=True, exist_ok=True)
