"""Web UI からのリクエストをまたいでジョブ状態を保持する。

アップロード済み PDF・プレビュー画像・生成中の進捗・生成結果を job_id(UUID4) を
キーにしたメモリ上の辞書で管理する。プロセス再起動で消えるのはローカルツールとして
許容する。
"""

import re
import shutil
import tempfile
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pymupdf

from repdf.pipeline import NormalizedBox, rasterize_page, sanitize

JobState = Literal["uploaded", "pending", "running", "done", "error"]

# create_job() が発行する UUID4 のみを受理する。job_id はそのまま URL パスや
# ファイルパスの一部として使われるため、この検証がパストラバーサル対策になる。
JOB_ID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)

_PREVIEW_DPI = 100
_PREVIEW_QUALITY = 85


@dataclass
class Job:
    id: str
    dir: Path
    page_count: int
    # 元 PDF の各ページの pt 単位サイズ(width, height)。アップロード時の情報提供用。
    page_sizes: list[tuple[float, float]]
    state: JobState = "uploaded"
    current: int = 0
    total: int = 0
    error: str | None = None
    has_markdown: bool = False
    has_audit: bool = False

    @property
    def input_pdf(self) -> Path:
        return self.dir / "input.pdf"

    @property
    def output_pdf(self) -> Path:
        return self.dir / "output.pdf"

    @property
    def output_markdown(self) -> Path:
        return self.dir / "output.md"

    @property
    def audit_json(self) -> Path:
        return self.dir / "audit.json"

    def preview_path(self, page_index: int) -> Path:
        return self.dir / f"preview-{page_index:04d}.jpg"


class JobStore:
    def __init__(self, base_dir: Path | None = None):
        self.base_dir = base_dir or (Path(tempfile.gettempdir()) / "repdf-jobs")
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def reset_base_dir(self) -> None:
        """アプリ起動時に呼ぶ。前回セッションの残骸を掃除して作り直す。"""
        if self.base_dir.exists():
            shutil.rmtree(self.base_dir)
        self.base_dir.mkdir(parents=True)
        with self._lock:
            self._jobs.clear()

    def create_job(self, pdf_bytes: bytes) -> Job:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        job_id = str(uuid.uuid4())
        job_dir = self.base_dir / job_id
        job_dir.mkdir(parents=True)

        input_path = job_dir / "input.pdf"
        input_path.write_bytes(pdf_bytes)

        doc = pymupdf.open(input_path)
        try:
            page_count = len(doc)
            page_sizes = [(p.rect.width, p.rect.height) for p in doc]
            job = Job(id=job_id, dir=job_dir, page_count=page_count, page_sizes=page_sizes)
            for i, page in enumerate(doc):
                image = rasterize_page(page, dpi=_PREVIEW_DPI)
                image.save(job.preview_path(i), format="JPEG", quality=_PREVIEW_QUALITY)
        finally:
            doc.close()

        with self._lock:
            self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        if not JOB_ID_PATTERN.match(job_id):
            return None
        with self._lock:
            return self._jobs.get(job_id)


def run_render(
    job: Job,
    *,
    remove_pages: set[int],
    boxes: dict[int, list[NormalizedBox]],
    dpi: int,
    text_layer: str,
    fill: str,
    ocr_lang: str,
    want_markdown: bool,
    want_audit: bool,
) -> None:
    """job.state を更新しながら sanitize() を実行する。FastAPI の BackgroundTasks から呼ぶ。"""
    job.state = "running"
    job.current = 0
    job.total = job.page_count - len(remove_pages)

    def on_progress(done: int, total: int) -> None:
        job.current = done
        job.total = total

    try:
        sanitize(
            job.input_pdf,
            job.output_pdf,
            remove_pages=remove_pages,
            boxes=boxes,
            dpi=dpi,
            text_layer=text_layer,
            fill=fill,
            ocr_lang=ocr_lang,
            markdown_path=job.output_markdown if want_markdown else None,
            audit_path=job.audit_json if want_audit else None,
            progress_callback=on_progress,
        )
        job.has_markdown = want_markdown
        job.has_audit = want_audit
        job.state = "done"
    except (ValueError, RuntimeError) as e:
        job.state = "error"
        job.error = str(e)
