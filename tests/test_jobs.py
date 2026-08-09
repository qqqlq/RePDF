import pymupdf
import pytest

from repdf.jobs import JOB_ID_PATTERN, JobStore, run_render


def make_pdf_bytes(page_count=2):
    doc = pymupdf.open()
    for i in range(page_count):
        doc.new_page().insert_text((72, 72), f"Page{i + 1} Visible", fontsize=14)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def store(tmp_path):
    return JobStore(base_dir=tmp_path / "jobs")


class TestCreateJob:
    def test_creates_job_with_correct_page_count(self, store):
        job = store.create_job(make_pdf_bytes(page_count=3))
        assert job.page_count == 3
        assert len(job.page_sizes) == 3

    def test_creates_preview_images_for_each_page(self, store):
        job = store.create_job(make_pdf_bytes(page_count=2))
        assert job.preview_path(0).exists()
        assert job.preview_path(1).exists()

    def test_job_id_matches_uuid_pattern(self, store):
        job = store.create_job(make_pdf_bytes())
        assert JOB_ID_PATTERN.match(job.id)

    def test_initial_state_is_uploaded(self, store):
        job = store.create_job(make_pdf_bytes())
        assert job.state == "uploaded"


class TestGet:
    def test_returns_created_job(self, store):
        job = store.create_job(make_pdf_bytes())
        assert store.get(job.id) is job

    def test_returns_none_for_unknown_uuid(self, store):
        assert store.get("00000000-0000-0000-0000-000000000000") is None

    def test_returns_none_for_path_traversal_attempt(self, store):
        assert store.get("../../etc/passwd") is None

    def test_returns_none_for_non_uuid_string(self, store):
        assert store.get("not-a-uuid") is None


class TestResetBaseDir:
    def test_clears_existing_jobs_and_files(self, store):
        job = store.create_job(make_pdf_bytes())
        assert job.dir.exists()
        store.reset_base_dir()
        assert not job.dir.exists()
        assert store.get(job.id) is None

    def test_recreates_empty_base_dir(self, store):
        store.reset_base_dir()
        assert store.base_dir.exists()


class TestRunRender:
    def test_successful_render_sets_done_state(self, store):
        job = store.create_job(make_pdf_bytes(page_count=2))
        run_render(
            job,
            remove_pages=set(),
            boxes={},
            dpi=100,
            text_layer="extract",
            fill="black",
            ocr_lang="eng",
            want_markdown=False,
            want_audit=False,
        )
        assert job.state == "done"
        assert job.output_pdf.exists()
        assert job.current == job.total == 2

    def test_render_respects_remove_pages_in_total(self, store):
        job = store.create_job(make_pdf_bytes(page_count=3))
        run_render(
            job,
            remove_pages={0},
            boxes={},
            dpi=100,
            text_layer="extract",
            fill="black",
            ocr_lang="eng",
            want_markdown=False,
            want_audit=False,
        )
        assert job.state == "done"
        assert job.total == 2

    def test_markdown_flag_produces_sidecar(self, store):
        job = store.create_job(make_pdf_bytes())
        run_render(
            job,
            remove_pages=set(),
            boxes={},
            dpi=100,
            text_layer="extract",
            fill="black",
            ocr_lang="eng",
            want_markdown=True,
            want_audit=False,
        )
        assert job.has_markdown is True
        assert job.output_markdown.exists()

    def test_invalid_combination_sets_error_state(self, store):
        job = store.create_job(make_pdf_bytes())
        run_render(
            job,
            remove_pages=set(),
            boxes={},
            dpi=100,
            text_layer="ocr",
            fill="black",
            ocr_lang="eng",
            want_markdown=False,
            want_audit=True,
        )
        assert job.state == "error"
        assert job.error is not None
