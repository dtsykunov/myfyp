#!/usr/bin/env sh
set -eu

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
ruff check "$repo_root/cloudflare/worker/src" "$repo_root/cloudflare/worker/tests"
