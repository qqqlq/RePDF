"""PDF サニタイズの中核処理: ラスタライズ・ページ選択・矩形塗り。

テキストレイヤーの生成(layer.py)・プロバイダ(providers.py)とはここでは疎結合にし、
このモジュールは「画像として PDF を扱う」部分だけを担う。
"""

from typing import Literal

import pymupdf
from PIL import Image, ImageDraw

FillColor = Literal["black", "white"]

# 正規化座標 (0.0-1.0) での矩形。(x0, y0, x1, y1)
NormalizedBox = tuple[float, float, float, float]

_FILL_RGB: dict[FillColor, tuple[int, int, int]] = {
    "black": (0, 0, 0),
    "white": (255, 255, 255),
}


def rasterize_page(page: pymupdf.Page, dpi: int) -> Image.Image:
    """ページを RGB 画像として描画する。"""
    pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB, alpha=False)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def apply_boxes(
    image: Image.Image,
    boxes: list[NormalizedBox],
    fill: FillColor = "black",
) -> Image.Image:
    """正規化座標(0.0-1.0)で指定された矩形を塗りつぶした画像を返す。

    dpi に依存しない正規化座標で受け取ることで、プレビュー用の低解像度画像で
    選択した範囲を、生成時の高解像度画像にもそのまま適用できる。
    """
    if not boxes:
        return image

    img = image.copy()
    draw = ImageDraw.Draw(img)
    width, height = img.size
    color = _FILL_RGB[fill]

    for x0, y0, x1, y1 in boxes:
        draw.rectangle(
            [x0 * width, y0 * height, x1 * width, y1 * height],
            fill=color,
        )
    return img


def pages_to_keep(page_count: int, remove_pages: set[int]) -> list[int]:
    """0-indexed の残すページ番号を昇順で返す。

    Args:
        page_count: 元 PDF の総ページ数。
        remove_pages: 削除する 0-indexed ページ番号の集合。
    """
    return [i for i in range(page_count) if i not in remove_pages]
