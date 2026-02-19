#!/usr/bin/env sh
set -eu

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$repo_root/cloudflare/worker"

port="${PORT:-8787}"
shim_path="$repo_root/cloudflare/worker/scripts"
pyodide_index="${MYFYP_PYODIDE_INDEX:-https://index.pyodide.org/0.29.3}"

if command -v pywrangler >/dev/null 2>&1; then
  exec env \
    PYTHONPATH="${shim_path}${PYTHONPATH:+:$PYTHONPATH}" \
    MYFYP_ENABLE_PYWRANGLER_PYODIDE_PATCH="1" \
    MYFYP_PYODIDE_INDEX="$pyodide_index" \
    pywrangler dev --config wrangler.toml --local --port "$port"
fi

if command -v uvx >/dev/null 2>&1; then
  exec env \
    PYTHONPATH="${shim_path}${PYTHONPATH:+:$PYTHONPATH}" \
    MYFYP_ENABLE_PYWRANGLER_PYODIDE_PATCH="1" \
    MYFYP_PYODIDE_INDEX="$pyodide_index" \
    uvx --from workers-py pywrangler dev --config wrangler.toml --local --port "$port"
fi

echo "Unable to find pywrangler. Install workers-py or use uvx." >&2
exit 1
