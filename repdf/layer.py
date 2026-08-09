"""画像の上に透明テキストレイヤーを重ねて、1ページ分の PDF を組み立てる。

OCR 方式・可視テキスト抽出方式のどちらから来た TextItem でも同じ経路で処理する。
PyMuPDF 組み込みの CJK フォント("japan")は ASCII も日本語も両方描画できるため、
言語によってフォントを切り替える必要はない(実測で確認済み。
docs/investigation-visibility-api.md 参照)。
"""

import io

import pymupdf
from PIL import Image

from repdf.models import TextItem

_FONTNAME = "japan"
# bbox の高さに対してフォントサイズをやや小さくする係数。
# ぴったりにすると行間で文字が隣の行にはみ出すことがあるための余裕。
_FONTSIZE_RATIO = 0.9

# ページ画像の JPEG 品質(0-100)。
# PNG で insert_image に渡すと PyMuPDF 1.28.2 では圧縮フィルタが付かず生ピクセルの
# まま埋め込まれ、ファイルサイズが実測で数十倍に膨らむことを確認したため JPEG を使う
# (A4 1ページ 200dpi で PNG 無圧縮 11.6MB → JPEG品質90で 数百KB)。
_JPEG_QUALITY = 90


def build_page(
    doc: pymupdf.Document,
    image: Image.Image,
    items: list[TextItem],
    page_rect: pymupdf.Rect,
) -> pymupdf.Page:
    """画像を敷き、TextItem を透明テキストとして重ねた新規ページを doc に追加する。

    ページサイズは page_rect(元 PDF ページの pt 単位サイズ)に合わせる。画像は
    高解像度(dpi 依存のピクセルサイズ)のまま渡してよく、insert_image がページ
    全体に縮小して敷く。TextItem の bbox も pt 単位(元ページ座標系)である前提。
    画像のピクセルサイズをそのまま pt として使うと、高 dpi でラスタライズした場合に
    実物より遥かに大きいページになってしまうため、これらを混同しないこと。
    """
    page = doc.new_page(width=page_rect.width, height=page_rect.height)

    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=_JPEG_QUALITY)
    page.insert_image(page.rect, stream=buf.getvalue())

    for item in items:
        _insert_transparent_text(page, item)

    return page


def _insert_transparent_text(page: pymupdf.Page, item: TextItem) -> None:
    x0, y0, x1, y1 = item.bbox
    height = y1 - y0
    if height <= 0 or not item.text:
        return

    fontsize = height * _FONTSIZE_RATIO
    origin = (x0, y1)  # insert_text の origin はベースライン位置。bbox 下端で近似する。

    try:
        page.insert_text(
            origin,
            item.text,
            fontsize=fontsize,
            fontname=_FONTNAME,
            render_mode=3,
        )
    except Exception:
        # グリフが存在しない等で失敗した場合、そのテキストは諦めて画像のみにする。
        # (隠しテキスト排除が目的のツールなので、失敗時に別の描画にフォールバックはしない)
        pass
