import pymupdf
import pytest
from PIL import Image

from repdf.layer import build_page
from repdf.models import TextItem


@pytest.fixture
def white_image():
    return Image.new("RGB", (300, 200), (255, 255, 255))


def test_build_page_matches_image_size(white_image):
    doc = pymupdf.open()
    build_page(doc, white_image, [])
    page = doc[0]
    assert page.rect.width == pytest.approx(300)
    assert page.rect.height == pytest.approx(200)
    doc.close()


def test_build_page_text_is_extractable(white_image):
    doc = pymupdf.open()
    items = [TextItem(text="Hello World", bbox=(10, 90, 150, 110), confidence=None)]
    page = build_page(doc, white_image, items)
    assert "Hello World" in page.get_text()
    doc.close()


def test_build_page_japanese_text_is_extractable(white_image):
    doc = pymupdf.open()
    items = [TextItem(text="こんにちは", bbox=(10, 90, 150, 110), confidence=None)]
    page = build_page(doc, white_image, items)
    assert "こんにちは" in page.get_text()
    doc.close()


def test_build_page_text_is_visually_invisible(white_image):
    doc = pymupdf.open()
    items = [TextItem(text="Secret", bbox=(10, 90, 150, 110), confidence=None)]
    page = build_page(doc, white_image, items)
    pix = page.get_pixmap()
    assert all(b == 255 for b in pix.samples)
    doc.close()


def test_build_page_preserves_multiple_items_order(white_image):
    doc = pymupdf.open()
    items = [
        TextItem(text="First", bbox=(10, 20, 100, 40), confidence=None),
        TextItem(text="Second", bbox=(10, 60, 100, 80), confidence=None),
    ]
    page = build_page(doc, white_image, items)
    extracted = page.get_text()
    assert extracted.index("First") < extracted.index("Second")
    doc.close()


def test_build_page_skips_zero_height_bbox(white_image):
    doc = pymupdf.open()
    items = [TextItem(text="Ghost", bbox=(10, 90, 150, 90), confidence=None)]
    page = build_page(doc, white_image, items)
    assert "Ghost" not in page.get_text()
    doc.close()


def test_build_page_skips_empty_text(white_image):
    doc = pymupdf.open()
    items = [TextItem(text="", bbox=(10, 90, 150, 110), confidence=None)]
    # 例外を出さずに完了すればよい
    build_page(doc, white_image, items)
    doc.close()
