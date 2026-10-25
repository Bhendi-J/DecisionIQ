#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"
npm --prefix frontend ci
npm --prefix frontend run build
if [[ "${INSTALL_PHISHING:-0}" == "1" ]]; then
  uv sync --locked --extra phishing
else
  uv sync --locked
fi
exec uv run --no-sync uvicorn decisioniq.main:app --host 127.0.0.1 --port "${DECISIONIQ_PORT:-8082}"
