#!/usr/bin/env sh
set -eu

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
export PYTHONPATH="${repo_root}/cloudflare/worker/src${PYTHONPATH:+:${PYTHONPATH}}"

exec uvicorn for_us_api.app:app --host 0.0.0.0 --port "${PORT:-8000}" --reload
