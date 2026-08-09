"""RePDF の Web UI 用 FastAPI アプリ。

認証機構を持たないため、既定では 127.0.0.1 にのみバインドする想定(run.sh 参照)。
"""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from repdf.jobs import Job, JobStore, run_render

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

job_store = JobStore()


def get_job_store() -> JobStore:
    return job_store


@asynccontextmanager
async def lifespan(app: FastAPI):
    job_store.reset_base_dir()
    yield


app = FastAPI(lifespan=lifespan)


def _get_job_or_404(job_id: str, store: JobStore) -> Job:
    job = store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job


@app.post("/api/upload")
async def upload(file: UploadFile, store: JobStore = Depends(get_job_store)):
    filename = (file.filename or "").lower()
    if file.content_type != "application/pdf" and not filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDFファイルを指定してください")

    data = await file.read()
    try:
        job = store.create_job(data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"PDFの読み込みに失敗しました: {e}") from e

    return {
        "jobId": job.id,
        "pageCount": job.page_count,
        "pages": [{"width": w, "height": h} for w, h in job.page_sizes],
    }


@app.get("/api/job/{job_id}/preview/{page}")
async def preview(job_id: str, page: int, store: JobStore = Depends(get_job_store)):
    job = _get_job_or_404(job_id, store)
    if page < 0 or page >= job.page_count:
        raise HTTPException(status_code=404, detail="page not found")
    path = job.preview_path(page)
    if not path.exists():
        raise HTTPException(status_code=404, detail="preview not found")
    return FileResponse(path, media_type="image/jpeg")


class RenderRequest(BaseModel):
    removePages: list[int] = []
    boxes: dict[str, list[list[float]]] = {}
    textLayer: Literal["extract", "ocr", "none"] = "extract"
    fill: Literal["black", "white"] = "black"
    dpi: int = 200
    ocrLang: str = "eng"
    markdown: bool = False
    audit: bool = False


@app.post("/api/job/{job_id}/render")
async def render(
    job_id: str,
    req: RenderRequest,
    background_tasks: BackgroundTasks,
    store: JobStore = Depends(get_job_store),
):
    job = _get_job_or_404(job_id, store)

    if req.audit and req.textLayer != "extract":
        raise HTTPException(
            status_code=400,
            detail='audit は textLayer="extract" のときのみ使用できます',
        )

    remove_pages = {p - 1 for p in req.removePages if p >= 1}
    try:
        boxes = {
            int(page_str) - 1: [tuple(box) for box in box_list]
            for page_str, box_list in req.boxes.items()
        }
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail="boxes の形式が不正です") from e

    job.state = "pending"
    background_tasks.add_task(
        run_render,
        job,
        remove_pages=remove_pages,
        boxes=boxes,
        dpi=req.dpi,
        text_layer=req.textLayer,
        fill=req.fill,
        ocr_lang=req.ocrLang,
        want_markdown=req.markdown,
        want_audit=req.audit,
    )
    return {"state": job.state}


@app.get("/api/job/{job_id}/status")
async def status(job_id: str, store: JobStore = Depends(get_job_store)):
    job = _get_job_or_404(job_id, store)
    return {
        "state": job.state,
        "current": job.current,
        "total": job.total,
        "error": job.error,
        "hasMarkdown": job.has_markdown,
        "hasAudit": job.has_audit,
    }


@app.get("/api/job/{job_id}/result.pdf")
async def result_pdf(job_id: str, store: JobStore = Depends(get_job_store)):
    job = _get_job_or_404(job_id, store)
    if job.state != "done" or not job.output_pdf.exists():
        raise HTTPException(status_code=404, detail="result not ready")
    return FileResponse(job.output_pdf, media_type="application/pdf", filename="sanitized.pdf")


@app.get("/api/job/{job_id}/result.md")
async def result_markdown(job_id: str, store: JobStore = Depends(get_job_store)):
    job = _get_job_or_404(job_id, store)
    if not job.has_markdown or not job.output_markdown.exists():
        raise HTTPException(status_code=404, detail="markdown not available")
    return FileResponse(job.output_markdown, media_type="text/markdown", filename="sanitized.md")


@app.get("/api/job/{job_id}/audit.json")
async def result_audit(job_id: str, store: JobStore = Depends(get_job_store)):
    job = _get_job_or_404(job_id, store)
    if not job.has_audit or not job.audit_json.exists():
        raise HTTPException(status_code=404, detail="audit report not available")
    return FileResponse(job.audit_json, media_type="application/json", filename="audit.json")


# API ルートより後にマウントする(先にマウントすると "/" 配下の全パスが StaticFiles に
# 食われて /api/... のルーティングが効かなくなる)。
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
