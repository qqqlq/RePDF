"""RePDF 全体で共有するデータモデル。"""

from dataclasses import dataclass

# PDF 点座標 (72dpi 基準) での矩形。(x0, y0, x1, y1)
BBox = tuple[float, float, float, float]


@dataclass(frozen=True)
class TextItem:
    """透明テキストレイヤーに配置する1要素。

    OCR プロバイダ・可視テキスト抽出プロバイダのどちらも、最終的にはこの形に
    変換する。レイヤー生成コード(layer.py)は方式を意識せずこれだけを扱う。
    """

    text: str
    bbox: BBox
    # OCR の信頼度(0-100)。抽出方式では常に None(信頼度という概念がないため)。
    confidence: float | None = None
