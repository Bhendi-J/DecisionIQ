#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"
npm --prefix frontend ci
npm --prefix frontend run build
if [[ "${INSTALL_PHISHING:-1}" == "1" ]]; then
  uv sync --locked --extra phishing
  uv run --no-sync python -m scripts.install_phishing_model
else
  uv sync --locked
fi
if [[ "${INSTALL_DEMO_DATA:-1}" == "1" ]]; then
  uv run --no-sync python -m scripts.install_demo_data
fi
exec uv run --no-sync uvicorn decisioniq.main:app --host 127.0.0.1 --port "${DECISIONIQ_PORT:-8082}"
