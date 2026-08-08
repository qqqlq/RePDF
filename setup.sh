#!/usr/bin/env bash
# RePDF のセットアップスクリプト。
# .venv を作成し、Python 依存関係を導入する。
# システム Python は PEP 668 (externally-managed) のため venv を必須にしている。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR=".venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "==> venv を作成: $VENV_DIR"
    python3 -m venv "$VENV_DIR"
fi

echo "==> 依存関係を導入"
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -r requirements-dev.txt

echo
echo "==> tesseract の確認"
if command -v tesseract >/dev/null 2>&1; then
    echo "OK: $(tesseract --version | head -1)"
    if ! tesseract --list-langs 2>/dev/null | grep -q '^jpn$'; then
        echo "注意: 日本語の学習データ (tesseract-ocr-jpn) が見つかりません。"
        echo "      OCR方式で日本語を扱う場合は以下を実行してください:"
        echo "      sudo apt install tesseract-ocr-jpn"
    fi
else
    echo "未検出: tesseract-ocr がインストールされていません。"
    echo "        OCR方式のテキストレイヤーは使えません(可視テキスト抽出方式は利用可能)。"
    echo "        OCR方式を使うには以下を実行してください:"
    echo "        sudo apt install tesseract-ocr tesseract-ocr-jpn"
fi

echo
echo "==> セットアップ完了"
echo "    source $VENV_DIR/bin/activate で venv を有効化してください"
