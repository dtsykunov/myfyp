#!/usr/bin/env sh
set -eu

pytest -q \
  --cov=src/for_us_api \
  --cov-report=term-missing:skip-covered \
  --cov-fail-under=95 \
  tests
