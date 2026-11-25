#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")"
python=${AUTOAPPLY_PYTHON:-"$PWD/backend/.venv/bin/python"}
if [[ ! -x "$python" || ! -f frontend/node_modules/vite/bin/vite.js ]]; then
  echo 'Dependencies are missing. Run make install (see README.md).' >&2
  exit 1
fi
if ! "$python" -c 'import fastapi, uvicorn' >/dev/null 2>&1; then
  echo 'The backend environment is broken. Recreate backend/.venv with Python 3.11, then run make install.' >&2
  exit 1
fi
api_port=${AUTOAPPLY_API_PORT:-8000}
ui_port=${AUTOAPPLY_UI_PORT:-5173}
if [[ "$ui_port" != 5173 && ! -v AUTOAPPLY_CORS_ORIGINS ]]; then
  export AUTOAPPLY_CORS_ORIGINS="http://localhost:$ui_port,http://127.0.0.1:$ui_port"
fi
(cd backend && PYTHONPATH=src exec "$python" -m uvicorn app.main:app --host 127.0.0.1 --port "$api_port") &
api=$!
(cd frontend && VITE_API_ROOT="http://127.0.0.1:$api_port" exec node node_modules/vite/bin/vite.js dev --host 127.0.0.1 --port "$ui_port" --strictPort) &
ui=$!
cleanup() {
  kill "$api" "$ui" 2>/dev/null || true
  wait "$api" "$ui" 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
printf 'AutoApply UI: http://localhost:%s\n' "$ui_port"
wait -n "$api" "$ui"
