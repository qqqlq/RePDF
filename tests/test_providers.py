import pymupdf
import pytest

from repdf.pipeline import rasterize_page
from repdf.providers import extract, ocr, parse_tesseract_tsv, tesseract_available


class TestExtract:
    @pytest.fixture
    def page(self):
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Visible", fontsize=12, render_mode=0)
        page.insert_text((72, 100), "Invisible", fontsize=12, render_mode=3)
        page.insert_text((72, 130), "WhiteOnWhite", fontsize=12, color=(1, 1, 1), render_mode=0)
        yield page
        doc.close()

    def test_only_visible_text_is_extracted(self, page):
        items = extract(page)
        texts = {item.text for item in items}
        assert texts == {"Visible"}

    def test_extracted_item_has_no_confidence(self, page):
        items = extract(page)
        assert all(item.confidence is None for item in items)

    def test_extracted_item_bbox_matches_span(self, page):
        items = extract(page)
        visible = next(item for item in items if item.text == "Visible")
        x0, y0, x1, y1 = visible.bbox
        assert x0 == pytest.approx(72.0, abs=1.0)
        assert x1 > x0
        assert y1 > y0

    def test_page_with_only_invisible_text_yields_nothing(self):
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Secret", fontsize=12, render_mode=3)
        assert extract(page) == []
        doc.close()


# tesseract の標準 TSV 出力ヘッダー(level=1がpage, 5がword)。
_TSV_HEADER = (
    "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\t"
    "left\ttop\twidth\theight\tconf\ttext"
)


def make_tsv(*rows: str) -> str:
    return "\n".join([_TSV_HEADER, *rows])


class TestParseTesseractTsv:
    def test_word_level_rows_are_extracted(self):
        tsv = make_tsv(
            "1\t1\t0\t0\t0\t0\t0\t0\t1000\t800\t-1\t",
            "5\t1\t1\t1\t1\t1\t100\t100\t90\t50\t95.5\tHello",
        )
        items = parse_tesseract_tsv(tsv, dpi=200)
        assert len(items) == 1
        assert items[0].text == "Hello"
        assert items[0].confidence == pytest.approx(95.5)

    def test_non_word_level_rows_are_ignored(self):
        tsv = make_tsv(
            "1\t1\t0\t0\t0\t0\t0\t0\t1000\t800\t-1\t",
            "2\t1\t1\t0\t0\t0\t100\t100\t200\t50\t-1\t",
            "3\t1\t1\t1\t0\t0\t100\t100\t200\t50\t-1\t",
            "4\t1\t1\t1\t1\t0\t100\t100\t200\t50\t-1\t",
        )
        assert parse_tesseract_tsv(tsv, dpi=200) == []

    def test_blank_text_word_rows_are_ignored(self):
        tsv = make_tsv("5\t1\t1\t1\t1\t1\t100\t100\t90\t50\t-1\t")
        assert parse_tesseract_tsv(tsv, dpi=200) == []

    def test_pixel_coordinates_are_converted_to_pdf_points(self):
        # dpi=200 の画像で left=100px -> pt = 100 * 72/200 = 36.0
        tsv = make_tsv("5\t1\t1\t1\t1\t1\t100\t100\t90\t50\t95.5\tHello")
        items = parse_tesseract_tsv(tsv, dpi=200)
        x0, y0, x1, y1 = items[0].bbox
        assert x0 == pytest.approx(36.0)
        assert y0 == pytest.approx(36.0)
        assert x1 == pytest.approx(36.0 + 90 * 72 / 200)
        assert y1 == pytest.approx(36.0 + 50 * 72 / 200)

    def test_empty_tsv_returns_empty_list(self):
        assert parse_tesseract_tsv("", dpi=200) == []

    def test_multiple_words_preserve_order(self):
        tsv = make_tsv(
            "5\t1\t1\t1\t1\t1\t100\t100\t90\t50\t95.5\tHello",
            "5\t1\t1\t1\t1\t2\t200\t100\t100\t50\t40.2\tWorld",
        )
        items = parse_tesseract_tsv(tsv, dpi=200)
        assert [item.text for item in items] == ["Hello", "World"]
        assert items[1].confidence == pytest.approx(40.2)


def test_tesseract_available_returns_bool():
    assert isinstance(tesseract_available(), bool)


@pytest.mark.skipif(not tesseract_available(), reason="tesseract がインストールされていない")
def test_ocr_reads_visible_text_from_rendered_page():
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello World", fontsize=24, render_mode=0)
    image = rasterize_page(page, dpi=200)
    doc.close()

    items = ocr(image, lang="eng", dpi=200)
    combined = " ".join(item.text for item in items)
    assert "Hello" in combined
    assert "World" in combined
