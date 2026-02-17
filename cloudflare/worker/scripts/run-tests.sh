#!/usr/bin/env sh
set -eu

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
PYTHONPATH="$repo_root/api/src:$repo_root/cloudflare/worker/src" pytest -q "$repo_root/cloudflare/worker/tests"
