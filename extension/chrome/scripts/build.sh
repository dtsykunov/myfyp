#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
chrome_dir="$(cd "${script_dir}/.." && pwd)"
repo_root="$(cd "${chrome_dir}/../.." && pwd)"
manifest_path="${chrome_dir}/manifest.json"
out_dir="${repo_root}/dist/extensions/chrome"

python_bin=""
if command -v python3 >/dev/null 2>&1; then
  python_bin="python3"
elif command -v python >/dev/null 2>&1; then
  python_bin="python"
else
  echo "python3 (or python) is required to build the Chrome extension package." >&2
  exit 1
fi

if ! command -v zip >/dev/null 2>&1; then
  echo "zip is required to build the Chrome extension package." >&2
  exit 1
fi

version="$("${python_bin}" - <<'PY' "${manifest_path}"
import json
import pathlib
import sys

manifest = pathlib.Path(sys.argv[1])
with manifest.open("r", encoding="utf-8") as file:
    data = json.load(file)

version_value = data.get("version")
if not isinstance(version_value, str) or not version_value.strip():
    raise SystemExit("manifest.json is missing a valid version string.")

print(version_value.strip())
PY
)"

mkdir -p "${out_dir}"
zip_path="${out_dir}/myfyp-chrome-v${version}.zip"

(
  cd "${chrome_dir}"
  zip -qr "${zip_path}" manifest.json background content popup icons
)

echo "Built Chrome extension package: ${zip_path}"
