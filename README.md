# RePDF

PDF から不要なページや領域を取り除き、隠しテキスト・メタデータ・注釈・スクリプトなどを
一切残さない状態で PDF を再生成するツール。

## 背景

PDF をそのまま AI に読み込ませる場合、目に見えない隠しテキスト（不可視レンダリングモードの
テキスト、背景色と同化した文字、メタデータなど）が混入していると、意図しない出力の原因に
なりうる。単純にページを削除するだけの方法では、残ったページの隠しテキストは消えない。

RePDF は全ページをラスタライズ（画像化）してから PDF を再構成することで、これらを物理的に
除去する。検索性を保つため、画像の上に透明なテキストレイヤーを再構築する
（OCR 方式 / 元テキストから可視なものだけを抽出する方式の 2 通りから選択可能）。

## 現在の状況

開発中。進め方の詳細は `docs/` を参照。

- [x] Phase 0: プロジェクト雛形
- [x] Phase 1: コアパイプライン・CLI
- [ ] Phase 2: Web UI
- [ ] Phase 3: 低信頼度レビュー・Claude 補正・Markdown 出力

詳細は `docs/phase1.md` を参照。

## セットアップ

```sh
./setup.sh
source .venv/bin/activate
```

OCR 方式のテキストレイヤーを使う場合は `tesseract-ocr` (と日本語なら `tesseract-ocr-jpn`) が
別途必要。`setup.sh` が未導入を検出した場合は案内を表示する。

## 使い方 (CLI)

```sh
python -m repdf.cli input.pdf -o output.pdf \
    --remove 3,5-7 \
    --dpi 200 \
    --text-layer extract \
    --boxes boxes.json \
    --fill black \
    --markdown output.md \
    --audit audit.json
```

| オプション | 説明 |
|---|---|
| `--remove` | 削除するページ(1-indexed)。例: `3,5-7` |
| `--dpi` | ラスタライズ解像度(既定: 200) |
| `--text-layer` | `extract`(元PDFの可視テキストを再利用)・`ocr`(tesseractで読み直す)・`none`(画像のみ) |
| `--boxes` | 黒塗り/白塗りする矩形を指定する JSON ファイル(1-indexedページ→正規化座標0.0-1.0の矩形配列) |
| `--fill` | `black` / `white`(既定: black) |
| `--ocr-lang` | `--text-layer ocr` のときの tesseract 言語指定(既定: eng。日本語は `jpn+eng`) |
| `--markdown` | 指定するとサニタイズ後のテキストを Markdown としても書き出す |
| `--audit` | `--text-layer extract` 専用。採用したテキストのうち OCR で検出できないものを警告 JSON に書き出す(tesseract 必須。詳細は `docs/audit-feature.md`) |

## 既知の制約

- ラスタライズにより出力ファイルサイズは大きくなる
- OCR 方式のテキストは原文と完全一致しない場合がある
- しおり・リンク・フォーム・注釈は失われる（サニタイズ目的の意図的な仕様）

## セキュリティに関する注意

このツールに認証機構はない。Web UI（Phase 2 以降）は既定で `127.0.0.1` にのみバインドする。
LAN 上の他端末から使いたい場合も、信頼できるネットワーク内でのみ、明示的なホスト指定を
した上で利用すること。

## チェンジログ

### Phase 1 追加機能: extract/OCR差分による監査レポート
- `--audit` オプションを追加。`--text-layer extract` が採用したテキストのうち、
  同じ位置を OCR しても検出できないものを警告 JSON に書き出す
- 可視判定(`visibility.py`)はヒューリスティクスであり、未知の隠し方(例: 白い図形で
  テキストを覆い隠す)を見逃す可能性がある。OCR は実際に画像へ描画されたものしか
  読めないため、この差分は「PDF上はテキストとして存在するが画像には描画されて
  いない」ことの強いシグナルになる。自動除去はせず警告に留める
- 詳細は `docs/audit-feature.md` を参照

### Phase 1
- ラスタライズ・ページ削除・黒塗り/白塗り・可視テキスト抽出・OCR・透明テキスト
  レイヤー・メタデータ除去・CLI・Markdown サイドカー出力を追加
- 詳細と既知の問題は `docs/phase1.md` を参照

### Phase 0
- プロジェクト雛形を追加（`.gitignore` / `LICENSE` / `requirements.txt` / `setup.sh`）
