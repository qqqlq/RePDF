"""TextItem 列から Markdown サイドカーを組み立てる。

AI に読ませる用途では、サニタイズ後の PDF そのものより、このテキストを直接渡す方が
確実(透明テキストレイヤーの再配置精度に左右されない)。

ここでの行組み立ては簡易的なもの: Y 座標が近い TextItem を同じ行とみなし、
X 座標順に連結する。低信頼度語のハイライトや Claude API による補正といった
発展的な機能は含まない(将来追加予定)。
"""

from repdf.models import TextItem

# 同じ行とみなす Y 座標の許容差(pt)。
_LINE_Y_TOLERANCE = 3.0


def items_to_markdown(items: list[TextItem]) -> str:
    """1 ページ分の TextItem を読み順(上から下、左から右)の Markdown テキストにする。"""
    if not items:
        return ""

    # bbox = (x0, y0, x1, y1)。まず上→下、同じ行内は左→右でソートする。
    ordered = sorted(items, key=lambda item: (item.bbox[1], item.bbox[0]))

    lines: list[list[str]] = []
    current_y: float | None = None
    for item in ordered:
        y0 = item.bbox[1]
        if current_y is None or abs(y0 - current_y) > _LINE_Y_TOLERANCE:
            lines.append([item.text])
            current_y = y0
        else:
            lines[-1].append(item.text)

    return "\n".join(" ".join(words) for words in lines)


def pages_to_markdown(pages_items: list[list[TextItem]]) -> str:
    """複数ページ分の TextItem を、ページ区切りを挟んだ 1つの Markdown にまとめる。"""
    pages_text = [items_to_markdown(items) for items in pages_items]
    return "\n\n---\n\n".join(pages_text)
