"""PDF サニタイズの中核処理: ラスタライズ・ページ選択・矩形塗り・全体の統合。"""

import os
from typing import Literal

import pymupdf
from PIL import Image, ImageDraw

from repdf.layer import build_page
from repdf.models import TextItem
from repdf.providers import extract, ocr
from repdf.visibility import DEFAULT_BACKGROUND_COLOR

FillColor = Literal["black", "white"]
TextLayerMode = Literal["extract", "ocr", "none"]

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


def _normalized_box_to_pt(box: NormalizedBox, page_rect: pymupdf.Rect) -> NormalizedBox:
    x0, y0, x1, y1 = box
    w, h = page_rect.width, page_rect.height
    return (x0 * w, y0 * h, x1 * w, y1 * h)


def _boxes_overlap(a: NormalizedBox, b: NormalizedBox) -> bool:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return not (ax1 <= bx0 or ax0 >= bx1 or ay1 <= by0 or ay0 >= by1)


def _drop_items_in_boxes(items: list[TextItem], boxes_pt: list[NormalizedBox]) -> list[TextItem]:
    """boxes_pt(pt単位)と重なる TextItem を除外する。

    text_layer="extract" は元PDFのテキストオブジェクトから直接読むため、画像側で
    黒塗り(apply_boxes)しても、その領域の元テキストはレイヤーにはそのまま残って
    しまう。塗った範囲の隠しテキストが結局残るという事故を防ぐため、抽出方式では
    ここで明示的に除外する(OCR方式は画像からしか読まないため自動的に除外される)。
    """
    if not boxes_pt:
        return items
    return [item for item in items if not any(_boxes_overlap(item.bbox, box) for box in boxes_pt)]


def pages_to_keep(page_count: int, remove_pages: set[int]) -> list[int]:
    """0-indexed の残すページ番号を昇順で返す。

    Args:
        page_count: 元 PDF の総ページ数。
        remove_pages: 削除する 0-indexed ページ番号の集合。
    """
    return [i for i in range(page_count) if i not in remove_pages]


def sanitize(
    input_path: str | os.PathLike[str],
    output_path: str | os.PathLike[str],
    *,
    remove_pages: set[int] | None = None,
    boxes: dict[int, list[NormalizedBox]] | None = None,
    dpi: int = 200,
    text_layer: TextLayerMode = "extract",
    fill: FillColor = "black",
    ocr_lang: str = "eng",
    background: tuple[float, float, float] = DEFAULT_BACKGROUND_COLOR,
) -> None:
    """PDF を丸ごとラスタライズして再構成し、隠しテキスト・メタデータを除去する。

    Args:
        remove_pages: 削除する 0-indexed ページ番号の集合。
        boxes: 0-indexed ページ番号 -> 正規化座標(0.0-1.0)の矩形リスト。
               ページ内の指定領域を fill 色で塗りつぶす(画像化した後に塗るため、
               その下に隠れているテキストは出力に一切現れない)。
        text_layer: "extract"(元PDFの可視テキストを再利用) / "ocr"(tesseractで
               読み直す) / "none"(画像のみ、検索不可)。
    """
    remove_pages = remove_pages or set()
    boxes = boxes or {}

    src_doc = pymupdf.open(str(input_path))
    try:
        out_doc = pymupdf.open()
        try:
            for src_index in pages_to_keep(len(src_doc), remove_pages):
                page = src_doc[src_index]
                page_boxes = boxes.get(src_index, [])
                image = rasterize_page(page, dpi)
                image = apply_boxes(image, page_boxes, fill=fill)

                if text_layer == "extract":
                    items = extract(page, background=background)
                    boxes_pt = [_normalized_box_to_pt(b, page.rect) for b in page_boxes]
                    items = _drop_items_in_boxes(items, boxes_pt)
                elif text_layer == "ocr":
                    items = ocr(image, lang=ocr_lang, dpi=dpi)
                elif text_layer == "none":
                    items = []
                else:
                    raise ValueError(f"unknown text_layer: {text_layer!r}")

                build_page(out_doc, image, items, page.rect)

            out_doc.set_metadata({})
            out_doc.del_xml_metadata()
            out_doc.save(str(output_path))
        finally:
            out_doc.close()
    finally:
        src_doc.close()
