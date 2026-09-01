#!/usr/bin/env bash
# Starts the service. Listens on $PORT (default 8080) and reads the upstream
# base URL from $FX_UPSTREAM_BASE (default https://api.frankfurter.dev).
# Nothing here hardcodes the real host.
set -euo pipefail
cd "$(dirname "$0")"

export FX_UPSTREAM_BASE="${FX_UPSTREAM_BASE:-https://api.frankfurter.dev}"
export PORT="${PORT:-8080}"

# Pick a Python >= 3.11 (the code uses 3.10+ typing syntax).
pick_python() {
  for candidate in python3.12 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1 &&
       "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 11) else 1)'; then
      echo "$candidate"; return 0
    fi
  done
  echo "Python 3.11+ is required. Try: brew install python@3.12" >&2
  return 1
}

if [[ ! -d .venv ]]; then
  PYTHON="$(pick_python)"
  "$PYTHON" -m venv .venv
  ./.venv/bin/pip install --quiet --upgrade pip
  ./.venv/bin/pip install --quiet -r requirements.txt
fi

exec ./.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
