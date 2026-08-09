"""テキストレイヤーの2方式: 可視テキスト抽出方式 / OCR方式。

どちらも最終的に list[TextItem] を返し、layer.py はどちらの方式で作られたかを
意識しない。
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

from repdf.models import TextItem
from repdf.visibility import DEFAULT_BACKGROUND_COLOR, is_visible_span

# tesseract TSV の word 行(level=5)の信頼度がこれ未満なら、テキストとして採用しない
# (負値は「非テキスト領域」を表すため、常に除外する)
_MIN_OCR_CONFIDENCE = 0.0


def extract(
    page,
    background: tuple[float, float, float] = DEFAULT_BACKGROUND_COLOR,
) -> list[TextItem]:
    """PDF の元テキストから、可視なものだけを抽出する。

    visibility.is_visible_span の判定に基づき、不可視の疑いがある span は
    一つでも除外条件に触れた時点で捨てる(安全側に倒す)。
    """
    items = []
    for span in page.get_texttrace():
        if not is_visible_span(span, page.cropbox, background=background):
            continue
        text = "".join(chr(c[0]) for c in span["chars"])
        if not text.strip():
            continue
        items.append(TextItem(text=text, bbox=tuple(span["bbox"]), confidence=None))
    return items


def tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


def ocr(image: Image.Image, lang: str = "eng", dpi: int = 200) -> list[TextItem]:
    """画像を tesseract に渡し、単語単位の座標付きテキストを取得する。

    tesseract の `pdf` 出力(画像+透明テキストが焼き込み済み)は使わず、`tsv` 出力を
    正として自前でレイヤーを組み立てる。理由: 低信頼度語の手修正を反映するには、
    座標と信頼度を個別に保持しておく必要があるため(layer.py で TextItem から
    透明テキストを配置する)。
    """
    if not tesseract_available():
        raise RuntimeError(
            "tesseract が見つかりません。OCR方式を使うには tesseract-ocr を導入してください"
            "(例: sudo apt install tesseract-ocr tesseract-ocr-jpn)。"
        )

    with tempfile.TemporaryDirectory() as tmp:
        img_path = Path(tmp) / "page.png"
        image.save(img_path)
        out_base = Path(tmp) / "out"
        subprocess.run(
            ["tesseract", str(img_path), str(out_base), "-l", lang, "tsv"],
            check=True,
            capture_output=True,
            text=True,
        )
        tsv_text = out_base.with_suffix(".tsv").read_text(encoding="utf-8")

    return parse_tesseract_tsv(tsv_text, dpi=dpi)


def parse_tesseract_tsv(tsv_text: str, dpi: int) -> list[TextItem]:
    """tesseract の TSV 出力を TextItem のリストに変換する。

    座標はピクセル単位(渡した画像の dpi 基準)で入っているため、PDF 点座標
    (72dpi 基準)に変換する。
    """
    lines = tsv_text.splitlines()
    if not lines:
        return []

    header = lines[0].split("\t")
    scale = 72.0 / dpi
    items = []

    for line in lines[1:]:
        if not line.strip():
            continue
        fields = line.split("\t")
        if len(fields) != len(header):
            continue
        row = dict(zip(header, fields, strict=True))

        # level=5 は単語単位の行。block/par/line/page 等の集計行は無視する。
        if row.get("level") != "5":
            continue

        text = row.get("text", "").strip()
        if not text:
            continue

        try:
            confidence = float(row["conf"])
        except (KeyError, ValueError):
            continue
        if confidence < _MIN_OCR_CONFIDENCE:
            continue

        try:
            left = float(row["left"]) * scale
            top = float(row["top"]) * scale
            width = float(row["width"]) * scale
            height = float(row["height"]) * scale
        except (KeyError, ValueError):
            continue

        items.append(
            TextItem(
                text=text,
                bbox=(left, top, left + width, top + height),
                confidence=confidence,
            )
        )

    return items
