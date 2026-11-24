#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3.10+ is required."
  exit 1
fi
python3 -c 'import sys; assert sys.version_info >= (3,10), "Python 3.10+ is required"'
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
if [ ! -f .env ]; then
  printf 'SESSION_SECRET=%s\nHOST=127.0.0.1\nCOOKIE_SECURE=false\n' "$(python -c 'import secrets; print(secrets.token_urlsafe(48))')" > .env
fi
PORT="$(python scripts/select_port.py)"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python scripts/open_browser_when_ready.py "http://127.0.0.1:${PORT}" &
echo "TourInsight: http://127.0.0.1:${PORT}"
echo "API docs:  http://127.0.0.1:${PORT}/docs"
python -m uvicorn backend.main:APP --host 127.0.0.1 --port "$PORT"
