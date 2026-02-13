from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ..settings import UPLOADS_DIR
from ..services import export_service, inventory, review_service, run_service
from .models import CellUpdateRequest, ExportRequest, RunRequest


router = APIRouter()


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/projects")
def list_projects() -> dict[str, list[dict[str, str]]]:
    return {"projects": [{"id": "default", "name": "Default Legal Review Project"}]}


@router.get("/documents")
def list_documents() -> dict[str, list[dict[str, str]]]:
    docs = inventory.sync_and_list_documents()
    return {
        "documents": [
            {
                "id": doc.id,
                "identifier": doc.identifier,
                "source": doc.source,
                "kind": doc.kind,
                "path": doc.path,
            }
            for doc in docs
        ]
    }


@router.post("/documents/upload")
async def upload_document(file: UploadFile = File(...)) -> dict[str, str]:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".pdf", ".html", ".htm"}:
        raise HTTPException(status_code=400, detail="Unsupported file type. Use PDF or HTML.")

    target = UPLOADS_DIR / (file.filename or "uploaded_document")
    with target.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)

    docs = inventory.sync_and_list_documents()
    uploaded = next((doc for doc in docs if doc.path == str(target.resolve())), None)

    return {
        "message": "uploaded",
        "document_id": uploaded.id if uploaded else "",
        "identifier": uploaded.identifier if uploaded else target.name,
    }


@router.post("/runs")
def run_extraction(request: RunRequest) -> dict:
    job_id = run_service.create_job(
        mode=request.mode,
        options={"template_path": request.template_path, "wait": request.wait},
    )

    if request.wait:
        run_service.run_job_sync(job_id, request.mode, request.template_path)
    else:
        run_service.run_job_async(job_id, request.mode, request.template_path)

    job = run_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=500, detail="Failed to create extraction job")
    return {"job": job}


@router.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    job = run_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job": job}


@router.get("/results/table")
def get_table(job_id: str | None = None) -> dict:
    return run_service.get_table_payload(job_id)


@router.patch("/cells/{cell_id}")
def update_cell(cell_id: str, request: CellUpdateRequest) -> dict:
    try:
        updated = review_service.update_cell(
            cell_id=cell_id,
            actor=request.actor,
            review_state=request.review_state,
            manual_value=request.manual_value,
            reason=request.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not updated:
        raise HTTPException(status_code=404, detail="Cell not found")

    return {"cell": updated}


@router.get("/cells/{cell_id}/audit")
def get_cell_audit(cell_id: str) -> dict:
    return {"logs": review_service.get_audit_logs(cell_id)}


@router.post("/exports/csv")
def export_csv(request: ExportRequest) -> FileResponse:
    path = export_service.export_csv(request.job_id)
    return FileResponse(path, media_type="text/csv", filename=path.name)


@router.post("/exports/xlsx")
def export_xlsx(request: ExportRequest) -> FileResponse:
    path = export_service.export_xlsx(request.job_id)
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=path.name,
    )
