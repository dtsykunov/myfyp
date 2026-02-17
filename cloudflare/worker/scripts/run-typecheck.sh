#!/usr/bin/env sh
set -eu

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
pyright --project "$repo_root/cloudflare/worker/pyrightconfig.json"
