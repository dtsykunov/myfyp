#!/usr/bin/env sh
set -eu

exec uvicorn for_us_api.app:app --host 0.0.0.0 --port "${PORT:-8000}" --reload

