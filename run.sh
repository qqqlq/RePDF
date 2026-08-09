#!/usr/bin/env bash
# RePDF の Web UI を起動する。
# このツールに認証機構はないため、既定では 127.0.0.1 にのみバインドする。
# LAN 上の他端末から使いたい場合は REPDF_HOST=0.0.0.0 のように明示指定すること
# (信頼できるネットワーク内でのみ利用してください)。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

HOST="${REPDF_HOST:-127.0.0.1}"
PORT="${REPDF_PORT:-8000}"

if [ "$HOST" != "127.0.0.1" ] && [ "$HOST" != "localhost" ]; then
    echo "警告: ${HOST} にバインドします。このツールに認証機構はありません。" >&2
    echo "      信頼できるネットワーク内でのみ使用してください。" >&2
fi

exec .venv/bin/uvicorn repdf.app:app --host "$HOST" --port "$PORT"
