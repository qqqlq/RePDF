"""PDF 内のテキストが「人間の目に見えるか」を判定するロジック。

可視テキスト抽出方式(providers.extract)の信頼性はすべてここに懸かっている。
判定はヒューリスティクスの積み重ねであり、**どれか一つでも不可視の疑いがあれば
除外する**(安全側に倒す)。根拠は docs/investigation-visibility-api.md の実測結果。

入力は pymupdf.Page.get_texttrace() が返す span 辞書。
"""

from typing import Any

# 不可視と判定するレンダリングモード(Tr 演算子)。
# 0=塗り 1=線 2=塗り+線 3=不可視 4-6=クリップ付き(描画される) 7=クリップのみ(不可視)
INVISIBLE_RENDER_MODES = frozenset({3, 7})

# 極小フォントとみなすサイズの閾値(pt)。これ未満は事実上判読不能として不可視扱いにする。
MIN_VISIBLE_FONT_SIZE = 1.0

# 背景色とみなす色(白)。ページごとの背景色推定は将来の課題とし、まずは白固定で開始する。
DEFAULT_BACKGROUND_COLOR: tuple[float, float, float] = (1.0, 1.0, 1.0)

# 色が「一致している」とみなす許容誤差。
_COLOR_MATCH_TOLERANCE = 1e-3


def _is_invisible_render_mode(span: dict[str, Any]) -> bool:
    return span.get("type") in INVISIBLE_RENDER_MODES


def _is_zero_opacity(span: dict[str, Any]) -> bool:
    opacity = span.get("opacity")
    return opacity is not None and opacity <= 0.0


def _matches_background_color(
    span: dict[str, Any],
    background: tuple[float, float, float],
    tolerance: float = _COLOR_MATCH_TOLERANCE,
) -> bool:
    color = span.get("color")
    if color is None:
        return False
    return all(abs(c - b) <= tolerance for c, b in zip(color, background, strict=True))


def _is_too_small(span: dict[str, Any], min_size: float = MIN_VISIBLE_FONT_SIZE) -> bool:
    size = span.get("size")
    return size is not None and size < min_size


def _is_outside_region(bbox: tuple[float, float, float, float], region) -> bool:
    """bbox が region(pymupdf.Rect 互換)と全く重ならないか、面積ゼロなら True。"""
    x0, y0, x1, y1 = bbox
    if x1 <= x0 or y1 <= y0:
        return True
    rx0, ry0, rx1, ry1 = region.x0, region.y0, region.x1, region.y1
    return x1 <= rx0 or x0 >= rx1 or y1 <= ry0 or y0 >= ry1


def is_visible_span(
    span: dict[str, Any],
    page_rect,
    background: tuple[float, float, float] = DEFAULT_BACKGROUND_COLOR,
) -> bool:
    """span が可視テキストとみなせるかどうかを判定する。

    Args:
        span: pymupdf.Page.get_texttrace() が返す span 辞書。
        page_rect: pymupdf.Rect 互換(x0, y0, x1, y1 属性を持つ)のページ範囲。
                   通常は page.cropbox を渡す。
        background: 背景色とみなす RGB (0.0-1.0)。
    """
    if _is_invisible_render_mode(span):
        return False
    if _is_zero_opacity(span):
        return False
    if _matches_background_color(span, background):
        return False
    if _is_too_small(span):
        return False
    if _is_outside_region(span.get("bbox", (0, 0, 0, 0)), page_rect):
        return False
    return True
