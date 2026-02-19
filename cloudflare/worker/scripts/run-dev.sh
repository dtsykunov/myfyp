#!/usr/bin/env sh
set -eu

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$repo_root/cloudflare/worker"

port="${PORT:-8787}"

if command -v pywrangler >/dev/null 2>&1; then
  exec pywrangler dev --config wrangler.toml --local --port "$port"
fi

if command -v uvx >/dev/null 2>&1; then
  exec uvx --from workers-py pywrangler dev --config wrangler.toml --local --port "$port"
fi

echo "Unable to find pywrangler. Install workers-py or use uvx." >&2
exit 1
