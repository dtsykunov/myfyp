#!/usr/bin/env sh
set -eu

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
PYTHONPATH="$repo_root/cloudflare/worker/src" pytest -q \
  --cov=for_us_shared \
  --cov=for_us_worker \
  --cov=entry \
  --cov-report=term-missing:skip-covered \
  --cov-fail-under=95 \
  "$repo_root/cloudflare/worker/tests"
