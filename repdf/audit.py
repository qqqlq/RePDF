"""extract 方式と OCR 方式の結果を突き合わせ、疑わしいテキストを検出する。

visibility.py の可視判定はヒューリスティクスの積み重ねであり、未知の隠し方
(未対応のブレンドモードや、背景色とわずかに異なる色など)には対応できない
可能性がある。OCR は実際に画像へ描画されたものしか読めないため、原理的な
保証がより強い。

extract() が「可視」と判定して残したテキストのうち、同じ位置を OCR しても
何も検出されない場合、それは「PDF 上はテキストとして存在するが、画像には
描画されていない」ことを意味し、可視判定の見落としである疑いが強い。
これを自動除去はせず、警告として報告し最終判断は利用者に委ねる。
"""

from dataclasses import dataclass

from repdf.models import BBox, TextItem

# 実PDFでの検証で、1文字だけの短いテキスト(数字・記号・単一アルファベット)は
# OCR が読み落としやすく、偽陽性の大半を占めることが分かったため判定対象から外す。
# 短い隠しテキストを見逃すリスクはあるが、ノイズだらけでは警告として機能しない。
_MIN_TEXT_LENGTH = 2


@dataclass(frozen=True)
class SuspiciousItem:
    text: str
    bbox: BBox
    reason: str


def _boxes_overlap(a: BBox, b: BBox) -> bool:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return not (ax1 <= bx0 or ax0 >= bx1 or ay1 <= by0 or ay0 >= by1)


def find_suspicious_items(
    extract_items: list[TextItem],
    ocr_items: list[TextItem],
) -> list[SuspiciousItem]:
    """extract_items のうち、ocr_items のどれとも位置が重ならないものを報告する。

    単語単位(OCR)と行単位(extract)で粒度が異なるため、判定は「一部でも重なって
    いれば対応するテキストとみなす」という緩めの基準にしている。OCR の読み落とし
    (低品質スキャン等)による誤検知はありうるため、これは自動除去ではなく警告。
    """
    suspicious = []
    for item in extract_items:
        if len(item.text.strip()) < _MIN_TEXT_LENGTH:
            continue
        if not any(_boxes_overlap(item.bbox, ocr_item.bbox) for ocr_item in ocr_items):
            suspicious.append(
                SuspiciousItem(text=item.text, bbox=item.bbox, reason="not_detected_by_ocr")
            )
    return suspicious
