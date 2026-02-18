#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
firefox_dir="$(cd "${script_dir}/.." && pwd)"
repo_root="$(cd "${firefox_dir}/../.." && pwd)"
manifest_path="${firefox_dir}/manifest.json"
out_dir="${repo_root}/dist/extensions/firefox"

python_bin=""
if command -v python3 >/dev/null 2>&1; then
  python_bin="python3"
elif command -v python >/dev/null 2>&1; then
  python_bin="python"
else
  echo "python3 (or python) is required to build the Firefox extension package." >&2
  exit 1
fi

if ! command -v zip >/dev/null 2>&1; then
  echo "zip is required to build the Firefox extension package." >&2
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
zip_path="${out_dir}/myfyp-firefox-v${version}.zip"

(
  cd "${firefox_dir}"
  zip -qr "${zip_path}" manifest.json background content popup
)

sha_path="${zip_path}.sha256"
"${python_bin}" - <<'PY' "${zip_path}" "${sha_path}"
from __future__ import annotations

import hashlib
import pathlib
import sys

zip_path = pathlib.Path(sys.argv[1])
sha_path = pathlib.Path(sys.argv[2])

digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
sha_path.write_text(f"{digest}  {zip_path.name}\n", encoding="utf-8")
PY

echo "Built Firefox extension package: ${zip_path}"
echo "Wrote checksum file: ${sha_path}"
