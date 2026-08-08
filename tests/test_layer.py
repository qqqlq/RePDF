import pymupdf
import pytest
from PIL import Image

from repdf.layer import build_page
from repdf.models import TextItem

# ページの物理サイズ(pt, 72dpi 基準)。画像はこれより高解像度で渡されることが多いので、
# テストでも意図的に画像サイズと異なる値にしている。
PAGE_RECT = pymupdf.Rect(0, 0, 300, 200)


@pytest.fixture
def white_image():
    # 200dpi でラスタライズした想定のピクセルサイズ(300pt, 200pt の約2.78倍)。
    return Image.new("RGB", (833, 556), (255, 255, 255))


def test_build_page_size_matches_page_rect_not_image_size(white_image):
    doc = pymupdf.open()
    build_page(doc, white_image, [], PAGE_RECT)
    page = doc[0]
    assert page.rect.width == pytest.approx(300)
    assert page.rect.height == pytest.approx(200)
    doc.close()


def test_build_page_text_is_extractable(white_image):
    doc = pymupdf.open()
    items = [TextItem(text="Hello World", bbox=(10, 90, 150, 110), confidence=None)]
    page = build_page(doc, white_image, items, PAGE_RECT)
    assert "Hello World" in page.get_text()
    doc.close()


def test_build_page_japanese_text_is_extractable(white_image):
    doc = pymupdf.open()
    items = [TextItem(text="こんにちは", bbox=(10, 90, 150, 110), confidence=None)]
    page = build_page(doc, white_image, items, PAGE_RECT)
    assert "こんにちは" in page.get_text()
    doc.close()


def test_build_page_text_is_visually_invisible(white_image):
    doc = pymupdf.open()
    items = [TextItem(text="Secret", bbox=(10, 90, 150, 110), confidence=None)]
    page = build_page(doc, white_image, items, PAGE_RECT)
    pix = page.get_pixmap()
    assert all(b == 255 for b in pix.samples)
    doc.close()


def test_build_page_preserves_multiple_items_order(white_image):
    doc = pymupdf.open()
    items = [
        TextItem(text="First", bbox=(10, 20, 100, 40), confidence=None),
        TextItem(text="Second", bbox=(10, 60, 100, 80), confidence=None),
    ]
    page = build_page(doc, white_image, items, PAGE_RECT)
    extracted = page.get_text()
    assert extracted.index("First") < extracted.index("Second")
    doc.close()


def test_build_page_skips_zero_height_bbox(white_image):
    doc = pymupdf.open()
    items = [TextItem(text="Ghost", bbox=(10, 90, 150, 90), confidence=None)]
    page = build_page(doc, white_image, items, PAGE_RECT)
    assert "Ghost" not in page.get_text()
    doc.close()


def test_build_page_skips_empty_text(white_image):
    doc = pymupdf.open()
    items = [TextItem(text="", bbox=(10, 90, 150, 110), confidence=None)]
    # 例外を出さずに完了すればよい
    build_page(doc, white_image, items, PAGE_RECT)
    doc.close()
