"""
Report Generator API routes.

Groups the report endpoints in one router:
  - Report generation (deterministic, non-agent) and retrieval/download.
  - The report field catalog (the checkbox list the UI exposes).

Reports are filled from the built-in default template
(components/report_generator/templates/report_template_{zh,en}.docx); the teacher
selects which fields to include via checkboxes and deselected fields are dropped.

Mounted by the report feature module (model_manager/features/report_feature.py)
through feature bootstrap during app startup.
"""

import asyncio
import json
import os
import logging
import shutil
import subprocess
from typing import Literal

from fastapi import APIRouter, File, HTTPException, UploadFile, Query
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse

from pipeline import Pipeline
from dto.report_dto import ReportRequest, ReportReselectRequest
from utils.runtime_config_loader import RuntimeConfig
from utils.storage_manager import StorageManager

logger = logging.getLogger(__name__)

router = APIRouter()


def _ensure_docx_report(session_id: str) -> tuple[str, str]:
    """Return ``(session_dir, docx_path)`` for a session report, creating .docx
    from markdown when needed.
    """
    from components.report_generator.docx_export import markdown_to_docx

    project_config = RuntimeConfig.get_section("Project")
    session_dir = os.path.join(
        project_config.get("location"),
        project_config.get("name"),
        session_id,
    )

    docx_path = os.path.join(session_dir, "class_report.docx")
    if os.path.exists(docx_path):
        return session_dir, docx_path

    report_md_path = os.path.join(session_dir, "class_report.md")
    if not os.path.exists(report_md_path):
        raise HTTPException(
            status_code=404,
            detail="Report not found. Generate it first.",
        )

    report_content = StorageManager.read_text_file(report_md_path)
    mindmap_path = os.path.join(session_dir, "mindmap_report.png")
    markdown_to_docx(
        report_content,
        docx_path,
        mindmap_image_path=mindmap_path if os.path.exists(mindmap_path) else None,
    )
    return session_dir, docx_path


@router.post("/report/generate")
async def generate_report(request: ReportRequest):
    """
    Generate a class evaluation report deterministically (non-agent).
    Fills the default template with the teacher-selected fields
    (request.selected_fields); deselected catalog fields are dropped.
    """
    pipeline = Pipeline(request.session_id)

    async def event_stream():
        try:
            for event in pipeline.run_report_generator(
                selected_fields=request.selected_fields,
                manual_fields=request.manual_fields,
            ):
                if isinstance(event, dict):
                    etype = event["type"]
                    if etype in ("partial_report", "report"):
                        yield json.dumps({"type": etype, "content": event.get("content", "")}) + "\n"
                    elif etype == "report_ready":
                        yield json.dumps({"type": "report_ready", "session_id": event.get("session_id", request.session_id)}) + "\n"
                    elif etype == "token":
                        content = event["content"]
                        if content.startswith("[ERROR]:"):
                            yield json.dumps({"token": "", "error": content}) + "\n"
                            break
                        yield json.dumps({"token": content, "error": ""}) + "\n"
                await asyncio.sleep(0)
        except HTTPException as e:
            detail = e.detail if isinstance(e.detail, str) else str(e.detail)
            yield json.dumps({"token": "", "error": f"[ERROR]: {detail}"}) + "\n"
        except Exception as e:
            logger.exception("Unexpected error while streaming report for session %s", request.session_id)
            yield json.dumps({"token": "", "error": f"[ERROR]: Report generation failed: {e}"}) + "\n"

    return StreamingResponse(event_stream(), media_type="application/json")


# ===== Report field catalog (the checkbox list the UI exposes) =====
# NOTE: This literal /report/... route is defined BEFORE the parametrized
# /report/{session_id} route below so FastAPI matches it first.

@router.get("/report/template-fields")
def get_report_template_fields():
    """Return the report field catalog (grouped, bilingual) for the checkboxes."""
    from components.report_generator.field_catalog import REPORT_TEMPLATE_FIELD_GROUPS
    return {"groups": REPORT_TEMPLATE_FIELD_GROUPS}


@router.post("/report/{session_id}/mindmap-image")
async def upload_mindmap_image(session_id: str, file: UploadFile = File(...)):
    """Store a mind-map PNG that the UI captured (html2canvas) from the live
    jsMind view, to be embedded in the class report.

    The report is a what-you-see-in-the-app image now: the frontend renders the
    mind map and screenshots it, so the backend never re-renders it. Saved as
    ``mindmap_report.png`` in the session dir — the exact path
    ReportGenerator picks up as the ``mindmap`` image field.
    """
    project_config = RuntimeConfig.get_section("Project")
    session_dir = os.path.join(
        project_config.get("location"),
        project_config.get("name"),
        session_id,
    )
    os.makedirs(session_dir, exist_ok=True)
    out_path = os.path.join(session_dir, "mindmap_report.png")

    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Empty mind-map image upload.")
        with open(out_path, "wb") as f:
            f.write(content)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Session {session_id}: failed to save mind-map image: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save mind-map image: {e}")

    logger.info(f"Session {session_id}: saved mind-map image ({len(content)} bytes) -> {out_path}")
    return JSONResponse(content={"session_id": session_id, "path": out_path}, status_code=200)


@router.get("/report/{session_id}/mindmap-image")
def get_mindmap_image(session_id: str):
    """Return the previously uploaded mind-map PNG for inline report preview."""
    project_config = RuntimeConfig.get_section("Project")
    image_path = os.path.join(
        project_config.get("location"),
        project_config.get("name"),
        session_id,
        "mindmap_report.png",
    )

    if not os.path.exists(image_path):
        raise HTTPException(
            status_code=404,
            detail=f"Mind-map image not found for session {session_id}.",
        )

    return FileResponse(
        path=image_path,
        media_type="image/png",
        filename="mindmap_report.png",
    )


# Parametrized report routes — defined AFTER the literal /report/template-fields
# route above so that literal is matched first.
@router.get("/report/{session_id}")
def get_report(session_id: str):
    """Retrieve a previously generated class report for a session."""
    project_config = RuntimeConfig.get_section("Project")
    report_path = os.path.join(
        project_config.get("location"),
        project_config.get("name"),
        session_id,
        "class_report.md",
    )

    if not os.path.exists(report_path):
        raise HTTPException(
            status_code=404,
            detail=f"Report not found for session {session_id}. Generate it first via POST /report/generate.",
        )

    report_content = StorageManager.read_text_file(report_path)
    return JSONResponse(
        content={"session_id": session_id, "report": report_content},
        status_code=200,
    )


@router.get("/report/{session_id}/download")
def download_report(
    session_id: str,
    format: Literal["docx", "pdf"] = Query("docx", description="Download format: docx or pdf"),
):
    """Download the class report in the requested format.

    Supported formats:
    - docx (default)
    - pdf (server-side conversion via LibreOffice headless)
    """
    session_dir, docx_path = _ensure_docx_report(session_id)

    if format == "docx":
        return FileResponse(
            path=docx_path,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename=f"class_report_{session_id}.docx",
        )

    pdf_path = os.path.join(session_dir, f"class_report_{session_id}.pdf")

    # Reuse cached PDF when it is up to date.
    if os.path.exists(pdf_path) and os.path.getmtime(pdf_path) >= os.path.getmtime(docx_path):
        return FileResponse(
            path=pdf_path,
            media_type="application/pdf",
            filename=f"class_report_{session_id}.pdf",
        )

    soffice = shutil.which("soffice")
    if not soffice:
        raise HTTPException(
            status_code=501,
            detail="PDF export is unavailable on server: LibreOffice (soffice) is not installed.",
        )

    try:
        subprocess.run(
            [
                soffice,
                "--headless",
                "--norestore",
                "--nolockcheck",
                "--convert-to",
                "pdf",
                "--outdir",
                session_dir,
                docx_path,
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        err = (e.stderr or e.stdout or "").strip()
        logger.error("PDF conversion failed for session %s: %s", session_id, err)
        raise HTTPException(status_code=500, detail="Failed to convert report to PDF.")

    default_pdf = os.path.join(session_dir, "class_report.pdf")
    if os.path.exists(default_pdf) and default_pdf != pdf_path:
        try:
            os.replace(default_pdf, pdf_path)
        except OSError:
            pdf_path = default_pdf

    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=500, detail="PDF conversion succeeded but output file was not found.")

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=f"class_report_{session_id}.pdf",
    )


@router.post("/report/{session_id}/reselect")
def reselect_report(session_id: str, request: ReportReselectRequest):
    """Re-render an existing report for a new checkbox selection — NO LLM.

    Re-projects the session's cached full-catalog fields onto the template,
    dropping the deselected fields. Instant and deterministic (same numbers/AI
    text as the last generation). Used when the teacher toggles fields after a
    report already exists; "Regenerate" is what recomputes the AI prose.
    """
    pipeline = Pipeline(session_id)
    result = pipeline.reapply_report_selection(
        selected_fields=request.selected_fields,
        manual_fields=request.manual_fields,
    )
    logger.info(f"Report re-projected for session {session_id} (no LLM).")
    return {"session_id": session_id, "message": "Report updated", **result}

