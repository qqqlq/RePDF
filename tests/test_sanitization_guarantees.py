"""RePDF の核となる保証を、実際の PDF 生成→サニタイズ→検証で確認する統合テスト。

各ユニットテスト(test_visibility.py 等)が個々のロジックを検証するのに対し、
ここでは「隠しテキストを詰め込んだ PDF を実際に sanitize() に通したとき、
最終的な PDF から本当に消えているか」を pdftotext (外部ツール) と PyMuPDF の
両方で確認する。どちらか一方の抽出方法にしか現れない残留があっても検知できるように。
"""

import subprocess

import pymupdf
import pytest

from repdf.pipeline import sanitize
from repdf.providers import tesseract_available

VISIBLE_TEXT = "PublicVisibleContent"
INVISIBLE_RENDER_MODE_TEXT = "SecretRenderMode3"
WHITE_ON_WHITE_TEXT = "SecretWhiteOnWhite"
OFF_PAGE_TEXT = "SecretOffPage"
ALL_HIDDEN_TEXTS = [INVISIBLE_RENDER_MODE_TEXT, WHITE_ON_WHITE_TEXT, OFF_PAGE_TEXT]


def _pdftotext(path) -> str:
    result = subprocess.run(
        ["pdftotext", str(path), "-"], capture_output=True, text=True, check=True
    )
    return result.stdout


@pytest.fixture
def booby_trapped_pdf(tmp_path):
    """可視テキスト・不可視テキスト3種・メタデータを詰め込んだ PDF。"""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), VISIBLE_TEXT, fontsize=14, render_mode=0)
    page.insert_text((72, 100), INVISIBLE_RENDER_MODE_TEXT, fontsize=14, render_mode=3)
    page.insert_text((72, 130), WHITE_ON_WHITE_TEXT, fontsize=14, color=(1, 1, 1), render_mode=0)
    page.insert_text((-500, -500), OFF_PAGE_TEXT, fontsize=14, render_mode=0)
    doc.set_metadata(
        {"title": "Secret Title", "author": "Secret Author", "keywords": "secret,keywords"}
    )
    path = tmp_path / "booby_trapped.pdf"
    doc.save(path)
    doc.close()
    return path


class TestExtractModeGuarantees:
    """text_layer="extract" (既定) での保証。"""

    @pytest.fixture
    def sanitized(self, booby_trapped_pdf, tmp_path):
        output = tmp_path / "out.pdf"
        sanitize(booby_trapped_pdf, output, dpi=150, text_layer="extract")
        return output

    def test_no_hidden_text_via_pymupdf(self, sanitized):
        doc = pymupdf.open(sanitized)
        all_text = "".join(page.get_text() for page in doc)
        doc.close()
        for hidden in ALL_HIDDEN_TEXTS:
            assert hidden not in all_text

    def test_no_hidden_text_via_pdftotext(self, sanitized):
        extracted = _pdftotext(sanitized)
        for hidden in ALL_HIDDEN_TEXTS:
            assert hidden not in extracted

    def test_visible_text_survives_via_pymupdf(self, sanitized):
        doc = pymupdf.open(sanitized)
        all_text = "".join(page.get_text() for page in doc)
        doc.close()
        assert VISIBLE_TEXT in all_text

    def test_visible_text_survives_via_pdftotext(self, sanitized):
        assert VISIBLE_TEXT in _pdftotext(sanitized)

    def test_metadata_is_empty(self, sanitized):
        doc = pymupdf.open(sanitized)
        metadata = doc.metadata
        doc.close()
        assert metadata["title"] == ""
        assert metadata["author"] == ""
        assert metadata["keywords"] == ""

    def test_page_count_preserved_when_nothing_removed(self, sanitized, booby_trapped_pdf):
        src = pymupdf.open(booby_trapped_pdf)
        out = pymupdf.open(sanitized)
        assert len(out) == len(src)
        src.close()
        out.close()


class TestNoneModeGuarantees:
    """text_layer="none" では検索性はゼロになるが、隠しテキストが出ないことは同じく保証する。"""

    def test_no_text_at_all(self, booby_trapped_pdf, tmp_path):
        output = tmp_path / "out.pdf"
        sanitize(booby_trapped_pdf, output, dpi=150, text_layer="none")
        assert _pdftotext(output).strip() == ""


class TestBoxRedactionGuarantees:
    """黒塗り指定した領域のテキストが、抽出方式でも残らないことの確認。"""

    def test_redacted_region_text_is_gone(self, tmp_path):
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((72, 72), VISIBLE_TEXT, fontsize=14, render_mode=0)
        page.insert_text((72, 300), "ShouldSurvive", fontsize=14, render_mode=0)
        input_path = tmp_path / "in.pdf"
        doc.save(input_path)
        doc.close()

        output = tmp_path / "out.pdf"
        # ページ上部(VISIBLE_TEXT のある領域)だけを黒塗りする
        sanitize(input_path, output, dpi=150, boxes={0: [(0.0, 0.0, 1.0, 0.2)]})

        extracted = _pdftotext(output)
        assert VISIBLE_TEXT not in extracted
        assert "ShouldSurvive" in extracted


@pytest.mark.skipif(not tesseract_available(), reason="tesseract がインストールされていない")
class TestOcrModeGuarantees:
    """text_layer="ocr" でも同じ保証が成り立つことの確認(緩めの一致でよい)。"""

    @pytest.fixture
    def sanitized(self, booby_trapped_pdf, tmp_path):
        output = tmp_path / "out.pdf"
        sanitize(booby_trapped_pdf, output, dpi=200, text_layer="ocr", ocr_lang="eng")
        return output

    def test_no_hidden_text(self, sanitized):
        extracted = _pdftotext(sanitized)
        for hidden in ALL_HIDDEN_TEXTS:
            assert hidden not in extracted

    def test_visible_text_is_recognized(self, sanitized):
        # OCR は完全一致まで求めず、主要な語幹が読み取れていればよしとする
        extracted = _pdftotext(sanitized)
        assert "Visible" in extracted or "PublicVisible" in extracted
