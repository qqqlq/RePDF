"""RePDF の CLI。

使用例:
    python -m repdf.cli input.pdf -o output.pdf \\
        --remove 3,5-7 --dpi 200 --text-layer extract \\
        --boxes boxes.json --fill black --markdown out.md --audit audit.json

ページ番号・boxes.json のキーはすべて 1-indexed(人間向け)。内部の sanitize() は
0-indexed で扱うため、ここで変換する。
"""

import argparse
import json
import sys

from repdf.pipeline import NormalizedBox, sanitize


def parse_page_ranges(spec: str) -> set[int]:
    """"3,5-7" のような 1-indexed 範囲指定を 0-indexed の集合に変換する。"""
    pages: set[int] = set()
    spec = spec.strip()
    if not spec:
        return pages

    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            start, end = int(start_s), int(end_s)
            if start < 1 or end < start:
                raise ValueError(f"不正なページ範囲: {part!r}")
            pages.update(range(start - 1, end))
        else:
            page = int(part)
            if page < 1:
                raise ValueError(f"不正なページ番号: {part!r}")
            pages.add(page - 1)
    return pages


def load_boxes(path: str) -> dict[int, list[NormalizedBox]]:
    """boxes.json ({"1": [[x0,y0,x1,y1], ...], "3": [...]}) を読み込む。

    キーは 1-indexed ページ番号、矩形は 0.0-1.0 の正規化座標。
    """
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    boxes: dict[int, list[NormalizedBox]] = {}
    for page_str, box_list in raw.items():
        page = int(page_str)
        if page < 1:
            raise ValueError(f"boxes.json のページ番号は1以上である必要があります: {page_str!r}")
        boxes[page - 1] = [tuple(box) for box in box_list]
    return boxes


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m repdf.cli",
        description="PDF をラスタライズして再構成し、隠しテキストやメタデータを除去する。",
    )
    parser.add_argument("input", help="入力 PDF のパス")
    parser.add_argument("-o", "--output", required=True, help="出力 PDF のパス")
    parser.add_argument(
        "--remove",
        default="",
        help="削除するページ(1-indexed)。例: 3,5-7",
    )
    parser.add_argument("--dpi", type=int, default=200, help="ラスタライズ解像度(既定: 200)")
    parser.add_argument(
        "--text-layer",
        choices=["extract", "ocr", "none"],
        default="extract",
        help="テキストレイヤーの方式(既定: extract)",
    )
    parser.add_argument(
        "--boxes",
        default=None,
        help="黒塗り/白塗りする矩形を指定する JSON ファイルのパス",
    )
    parser.add_argument(
        "--fill",
        choices=["black", "white"],
        default="black",
        help="矩形塗りつぶしの色(既定: black)",
    )
    parser.add_argument(
        "--ocr-lang",
        default="eng",
        help="--text-layer ocr のときの tesseract 言語指定(既定: eng。日本語は jpn+eng など)",
    )
    parser.add_argument(
        "--markdown",
        default=None,
        help="指定するとサニタイズ後のテキストを Markdown としても書き出す",
    )
    parser.add_argument(
        "--audit",
        default=None,
        help=(
            "指定すると、--text-layer extract で採用したテキストのうち、同じ位置を"
            " OCR しても検出できないものを警告として JSON に書き出す"
            "(--text-layer extract 専用。tesseract が必要)"
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    try:
        remove_pages = parse_page_ranges(args.remove)
        boxes = load_boxes(args.boxes) if args.boxes else None
    except (ValueError, OSError, json.JSONDecodeError) as e:
        print(f"エラー: {e}", file=sys.stderr)
        return 1

    try:
        sanitize(
            args.input,
            args.output,
            remove_pages=remove_pages,
            boxes=boxes,
            dpi=args.dpi,
            text_layer=args.text_layer,
            fill=args.fill,
            ocr_lang=args.ocr_lang,
            markdown_path=args.markdown,
            audit_path=args.audit,
        )
    except (RuntimeError, ValueError) as e:
        print(f"エラー: {e}", file=sys.stderr)
        return 1

    print(f"出力しました: {args.output}")
    if args.markdown:
        print(f"Markdown も出力しました: {args.markdown}")
    if args.audit:
        with open(args.audit, encoding="utf-8") as f:
            report = json.load(f)
        count = len(report["suspicious_items"])
        print(f"監査レポートを出力しました: {args.audit} (疑わしいテキスト {count} 件)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
