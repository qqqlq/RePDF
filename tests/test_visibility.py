"""visibility.py の単体テスト。

is_visible_span は「安全側に倒す(疑わしきは不可視)」判定なので、各ヒューリスティクス
が単独で不可視判定を出すこと、および素直な可視ケースが誤って除外されないことを確認する。
"""

import pymupdf
import pytest

from repdf.visibility import is_visible_span

PAGE_RECT = pymupdf.Rect(0, 0, 595, 842)


def make_span(**overrides):
    span = {
        "type": 0,
        "opacity": 1.0,
        "color": (0.0, 0.0, 0.0),
        "size": 12.0,
        "bbox": (72.0, 72.0, 120.0, 90.0),
    }
    span.update(overrides)
    return span


def test_normal_visible_text_is_visible():
    assert is_visible_span(make_span(), PAGE_RECT) is True


@pytest.mark.parametrize("render_mode", [3, 7])
def test_invisible_render_mode_is_excluded(render_mode):
    assert is_visible_span(make_span(type=render_mode), PAGE_RECT) is False


@pytest.mark.parametrize("render_mode", [1, 2, 4, 5, 6])
def test_other_render_modes_are_not_excluded_by_render_mode_alone(render_mode):
    # クリップ用途(4-6)や線描画(1,2)は見た目に描画されるため、type だけでは除外しない
    assert is_visible_span(make_span(type=render_mode), PAGE_RECT) is True


def test_zero_opacity_is_excluded():
    assert is_visible_span(make_span(opacity=0.0), PAGE_RECT) is False


def test_white_on_white_is_excluded():
    assert is_visible_span(make_span(color=(1.0, 1.0, 1.0)), PAGE_RECT) is False


def test_near_white_within_tolerance_is_excluded():
    assert is_visible_span(make_span(color=(0.9999, 0.9999, 0.9999)), PAGE_RECT) is False


def test_black_text_is_not_excluded_by_color():
    assert is_visible_span(make_span(color=(0.0, 0.0, 0.0)), PAGE_RECT) is True


def test_tiny_font_is_excluded():
    assert is_visible_span(make_span(size=0.5), PAGE_RECT) is False


def test_font_size_exactly_at_threshold_is_not_excluded():
    # MIN_VISIBLE_FONT_SIZE = 1.0 pt ちょうどは「未満」ではないので可視扱い
    assert is_visible_span(make_span(size=1.0), PAGE_RECT) is True


def test_text_fully_outside_page_is_excluded():
    assert is_visible_span(make_span(bbox=(-500, -500, -400, -480)), PAGE_RECT) is False


def test_zero_area_bbox_is_excluded():
    assert is_visible_span(make_span(bbox=(72.0, 72.0, 72.0, 90.0)), PAGE_RECT) is False


def test_text_partially_overlapping_page_is_not_excluded():
    # ページ端からはみ出していても、一部でも重なっていれば可視として扱う
    assert is_visible_span(make_span(bbox=(-10.0, 72.0, 50.0, 90.0)), PAGE_RECT) is True


def test_multiple_reasons_still_excluded():
    span = make_span(type=3, opacity=0.0, color=(1.0, 1.0, 1.0), size=0.1)
    assert is_visible_span(span, PAGE_RECT) is False


class TestAgainstRealPdf:
    """実際に PyMuPDF で PDF を生成し、get_texttrace() 経由での判定を確認する。"""

    @pytest.fixture
    def page(self):
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Visible", fontsize=12, render_mode=0)
        page.insert_text((72, 100), "Invisible", fontsize=12, render_mode=3)
        page.insert_text((72, 130), "WhiteOnWhite", fontsize=12, color=(1, 1, 1), render_mode=0)
        yield page
        doc.close()

    def test_real_spans_are_classified_correctly(self, page):
        results = {}
        for span in page.get_texttrace():
            text = "".join(chr(c[0]) for c in span["chars"])
            results[text] = is_visible_span(span, page.cropbox)

        assert results["Visible"] is True
        assert results["Invisible"] is False
        assert results["WhiteOnWhite"] is False
