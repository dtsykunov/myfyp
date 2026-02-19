#!/usr/bin/env sh
set -eu

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
export PYTHONPATH="${repo_root}/cloudflare/worker/src${PYTHONPATH:+:${PYTHONPATH}}"

pytest -q \
  --cov=src/for_us_api \
  --cov-report=term-missing:skip-covered \
  --cov-fail-under=95 \
  tests
