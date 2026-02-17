#!/usr/bin/env sh
set -eu

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
if ! python -c "import pytest_cov" >/dev/null 2>&1; then
  pip install --no-cache-dir pytest-cov >/dev/null
fi
PYTHONPATH="$repo_root/cloudflare/worker/src" pytest -q \
  --cov=for_us_shared \
  --cov=for_us_worker \
  --cov=entry \
  --cov-report=term-missing:skip-covered \
  --cov-fail-under=95 \
  "$repo_root/cloudflare/worker/tests"
