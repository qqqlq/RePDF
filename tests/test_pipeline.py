import pymupdf
import pytest
from PIL import Image

from repdf.pipeline import apply_boxes, pages_to_keep, rasterize_page


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
