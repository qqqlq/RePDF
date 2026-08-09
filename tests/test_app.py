import io

import pymupdf
import pytest
from fastapi.testclient import TestClient

from repdf.app import app, get_job_store
from repdf.jobs import JobStore
from repdf.providers import tesseract_available


def make_pdf_bytes(page_count=2):
    doc = pymupdf.open()
    for i in range(page_count):
        doc.new_page().insert_text((72, 72), f"Page{i + 1} Visible", fontsize=14)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def client(tmp_path):
    test_store = JobStore(base_dir=tmp_path / "jobs")
    test_store.reset_base_dir()
    app.dependency_overrides[get_job_store] = lambda: test_store
    # TestClient を `with` なしで使うと lifespan(=グローバル job_store のリセット)は
    # 実行されない。テストが本番用の一時ディレクトリに触れないようにするため。
    yield TestClient(app)
    app.dependency_overrides.clear()


def upload(client, page_count=2):
    files = {"file": ("test.pdf", io.BytesIO(make_pdf_bytes(page_count)), "application/pdf")}
    return client.post("/api/upload", files=files)


class TestUpload:
    def test_returns_job_id_and_page_count(self, client):
        res = upload(client, page_count=3)
        assert res.status_code == 200
        data = res.json()
        assert "jobId" in data
        assert data["pageCount"] == 3
        assert len(data["pages"]) == 3

    def test_rejects_non_pdf_file(self, client):
        files = {"file": ("test.txt", io.BytesIO(b"not a pdf"), "text/plain")}
        res = client.post("/api/upload", files=files)
        assert res.status_code == 400

    def test_rejects_corrupt_pdf(self, client):
        files = {"file": ("test.pdf", io.BytesIO(b"%PDF-1.4 garbage"), "application/pdf")}
        res = client.post("/api/upload", files=files)
        assert res.status_code == 400


class TestPreview:
    def test_returns_jpeg_image(self, client):
        job_id = upload(client).json()["jobId"]
        res = client.get(f"/api/job/{job_id}/preview/0")
        assert res.status_code == 200
        assert res.headers["content-type"] == "image/jpeg"

    def test_out_of_range_page_returns_404(self, client):
        job_id = upload(client, page_count=2).json()["jobId"]
        res = client.get(f"/api/job/{job_id}/preview/5")
        assert res.status_code == 404

    def test_unknown_job_id_returns_404(self, client):
        res = client.get("/api/job/00000000-0000-0000-0000-000000000000/preview/0")
        assert res.status_code == 404

    def test_path_traversal_job_id_returns_404(self, client):
        res = client.get("/api/job/../../etc/preview/0")
        assert res.status_code == 404


class TestRender:
    def test_full_flow_produces_downloadable_pdf(self, client):
        job_id = upload(client, page_count=2).json()["jobId"]
        res = client.post(f"/api/job/{job_id}/render", json={"dpi": 100})
        assert res.status_code == 200

        status = client.get(f"/api/job/{job_id}/status").json()
        assert status["state"] == "done"
        assert status["current"] == status["total"] == 2

        result = client.get(f"/api/job/{job_id}/result.pdf")
        assert result.status_code == 200
        assert result.headers["content-type"] == "application/pdf"

    def test_remove_pages_reduces_output(self, client):
        job_id = upload(client, page_count=3).json()["jobId"]
        client.post(f"/api/job/{job_id}/render", json={"dpi": 100, "removePages": [2]})
        status = client.get(f"/api/job/{job_id}/status").json()
        assert status["total"] == 2

        result = client.get(f"/api/job/{job_id}/result.pdf")
        out_doc = pymupdf.open(stream=result.content, filetype="pdf")
        try:
            assert len(out_doc) == 2
        finally:
            out_doc.close()

    def test_audit_with_non_extract_text_layer_returns_400(self, client):
        job_id = upload(client).json()["jobId"]
        res = client.post(
            f"/api/job/{job_id}/render",
            json={"dpi": 100, "textLayer": "none", "audit": True},
        )
        assert res.status_code == 400

    def test_markdown_flag_makes_result_md_available(self, client):
        job_id = upload(client).json()["jobId"]
        client.post(f"/api/job/{job_id}/render", json={"dpi": 100, "markdown": True})
        status = client.get(f"/api/job/{job_id}/status").json()
        assert status["hasMarkdown"] is True
        res = client.get(f"/api/job/{job_id}/result.md")
        assert res.status_code == 200

    def test_result_md_404_when_not_generated(self, client):
        job_id = upload(client).json()["jobId"]
        client.post(f"/api/job/{job_id}/render", json={"dpi": 100})
        res = client.get(f"/api/job/{job_id}/result.md")
        assert res.status_code == 404

    def test_boxes_are_applied(self, client):
        job_id = upload(client, page_count=1).json()["jobId"]
        res = client.post(
            f"/api/job/{job_id}/render",
            json={"dpi": 100, "boxes": {"1": [[0.0, 0.0, 1.0, 0.3]]}},
        )
        assert res.status_code == 200
        status = client.get(f"/api/job/{job_id}/status").json()
        assert status["state"] == "done"

    def test_unknown_job_id_returns_404(self, client):
        res = client.post(
            "/api/job/00000000-0000-0000-0000-000000000000/render", json={"dpi": 100}
        )
        assert res.status_code == 404

    @pytest.mark.skipif(not tesseract_available(), reason="tesseract がインストールされていない")
    def test_audit_flag_makes_audit_json_available(self, client):
        job_id = upload(client).json()["jobId"]
        client.post(
            f"/api/job/{job_id}/render",
            json={"dpi": 150, "textLayer": "extract", "audit": True},
        )
        status = client.get(f"/api/job/{job_id}/status").json()
        assert status["hasAudit"] is True
        res = client.get(f"/api/job/{job_id}/audit.json")
        assert res.status_code == 200
        assert "suspicious_items" in res.json()


class TestStatus:
    def test_unknown_job_id_returns_404(self, client):
        res = client.get("/api/job/00000000-0000-0000-0000-000000000000/status")
        assert res.status_code == 404

    def test_uploaded_job_before_render_has_uploaded_state(self, client):
        job_id = upload(client).json()["jobId"]
        res = client.get(f"/api/job/{job_id}/status")
        assert res.json()["state"] == "uploaded"


class TestResultPdf:
    def test_not_ready_before_render_returns_404(self, client):
        job_id = upload(client).json()["jobId"]
        res = client.get(f"/api/job/{job_id}/result.pdf")
        assert res.status_code == 404


class TestStaticFrontend:
    def test_index_html_is_served(self, client):
        res = client.get("/")
        assert res.status_code == 200
        assert "text/html" in res.headers["content-type"]

    def test_app_js_is_served(self, client):
        res = client.get("/app.js")
        assert res.status_code == 200
