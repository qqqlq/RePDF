import pymupdf
import pytest
from PIL import Image

from repdf.pipeline import apply_boxes, pages_to_keep, rasterize_page, sanitize


@pytest.fixture
def page():
    doc = pymupdf.open()
    page = doc.new_page(width=200, height=100)
    page.insert_text((10, 20), "hello", fontsize=12)
    yield page
    doc.close()


def test_rasterize_page_returns_correct_pixel_size(page):
    image = rasterize_page(page, dpi=72)
    # 72dpi は PDF の pt と 1:1 なので、ページサイズ通りのピクセル数になる
    assert image.size == (200, 100)
    assert image.mode == "RGB"


def test_rasterize_page_scales_with_dpi(page):
    image = rasterize_page(page, dpi=144)
    assert image.size == (400, 200)


def test_apply_boxes_with_no_boxes_returns_unchanged_image():
    image = Image.new("RGB", (100, 100), (255, 255, 255))
    result = apply_boxes(image, [], fill="black")
    assert result.getpixel((50, 50)) == (255, 255, 255)


def test_apply_boxes_paints_black_region():
    image = Image.new("RGB", (100, 100), (255, 255, 255))
    result = apply_boxes(image, [(0.0, 0.0, 0.5, 0.5)], fill="black")
    assert result.getpixel((10, 10)) == (0, 0, 0)
    assert result.getpixel((90, 90)) == (255, 255, 255)


def test_apply_boxes_paints_white_region():
    image = Image.new("RGB", (100, 100), (0, 0, 0))
    result = apply_boxes(image, [(0.5, 0.5, 1.0, 1.0)], fill="white")
    assert result.getpixel((90, 90)) == (255, 255, 255)
    assert result.getpixel((10, 10)) == (0, 0, 0)


def test_apply_boxes_does_not_mutate_original_image():
    image = Image.new("RGB", (100, 100), (255, 255, 255))
    apply_boxes(image, [(0.0, 0.0, 1.0, 1.0)], fill="black")
    assert image.getpixel((50, 50)) == (255, 255, 255)


def test_pages_to_keep_removes_specified_pages():
    assert pages_to_keep(page_count=10, remove_pages={2, 4, 6}) == [0, 1, 3, 5, 7, 8, 9]


def test_pages_to_keep_with_no_removals_keeps_all():
    assert pages_to_keep(page_count=3, remove_pages=set()) == [0, 1, 2]


def test_pages_to_keep_with_all_removed_returns_empty():
    assert pages_to_keep(page_count=3, remove_pages={0, 1, 2}) == []


class TestSanitize:
    @pytest.fixture
    def input_pdf(self, tmp_path):
        doc = pymupdf.open()
        p1 = doc.new_page()
        p1.insert_text((72, 72), "Page1 Visible", fontsize=14, render_mode=0)
        p1.insert_text((72, 100), "Page1 SecretHidden", fontsize=14, render_mode=3)
        doc.new_page().insert_text((72, 72), "Page2 ToBeDeleted", fontsize=14, render_mode=0)
        doc.new_page().insert_text((72, 72), "Page3 Visible", fontsize=14, render_mode=0)
        doc.set_metadata({"title": "Secret Title", "author": "Secret Author"})
        path = tmp_path / "input.pdf"
        doc.save(path)
        doc.close()
        return path

    def test_removes_specified_pages(self, input_pdf, tmp_path):
        output = tmp_path / "output.pdf"
        sanitize(input_pdf, output, remove_pages={1}, dpi=100)
        out_doc = pymupdf.open(output)
        try:
            assert len(out_doc) == 2
            assert "Page1 Visible" in out_doc[0].get_text()
            assert "Page3 Visible" in out_doc[1].get_text()
            assert "ToBeDeleted" not in out_doc[0].get_text() + out_doc[1].get_text()
        finally:
            out_doc.close()

    def test_hidden_text_does_not_survive(self, input_pdf, tmp_path):
        output = tmp_path / "output.pdf"
        sanitize(input_pdf, output, dpi=100)
        out_doc = pymupdf.open(output)
        try:
            all_text = "".join(page.get_text() for page in out_doc)
            assert "SecretHidden" not in all_text
        finally:
            out_doc.close()

    def test_metadata_is_cleared(self, input_pdf, tmp_path):
        output = tmp_path / "output.pdf"
        sanitize(input_pdf, output, dpi=100)
        out_doc = pymupdf.open(output)
        try:
            assert out_doc.metadata["title"] == ""
            assert out_doc.metadata["author"] == ""
        finally:
            out_doc.close()

    def test_text_layer_none_produces_no_text(self, input_pdf, tmp_path):
        output = tmp_path / "output.pdf"
        sanitize(input_pdf, output, dpi=100, text_layer="none")
        out_doc = pymupdf.open(output)
        try:
            assert all(page.get_text().strip() == "" for page in out_doc)
        finally:
            out_doc.close()

    def test_boxes_remove_text_in_region(self, input_pdf, tmp_path):
        output = tmp_path / "output.pdf"
        # ページ0(0-indexed)の上半分を黒塗り("Page1 Visible"はページ上部にある)
        sanitize(input_pdf, output, dpi=100, boxes={0: [(0.0, 0.0, 1.0, 0.3)]})
        out_doc = pymupdf.open(output)
        try:
            assert "Page1 Visible" not in out_doc[0].get_text()
        finally:
            out_doc.close()

    def test_invalid_text_layer_raises(self, input_pdf, tmp_path):
        output = tmp_path / "output.pdf"
        with pytest.raises(ValueError):
            sanitize(input_pdf, output, dpi=100, text_layer="bogus")

    def test_markdown_sidecar_is_written(self, input_pdf, tmp_path):
        output = tmp_path / "output.pdf"
        markdown_path = tmp_path / "output.md"
        sanitize(input_pdf, output, remove_pages={1}, dpi=100, markdown_path=markdown_path)
        content = markdown_path.read_text(encoding="utf-8")
        assert "Page1 Visible" in content
        assert "Page3 Visible" in content
        assert "SecretHidden" not in content

    def test_markdown_sidecar_not_written_when_path_omitted(self, input_pdf, tmp_path):
        output = tmp_path / "output.pdf"
        sanitize(input_pdf, output, dpi=100)
        assert not (tmp_path / "output.md").exists()
