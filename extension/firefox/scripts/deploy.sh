#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../../.." && pwd)"
firefox_dir="$(cd "${script_dir}/.." && pwd)"
out_dir="${repo_root}/dist/extensions/firefox"
manifest_path="${firefox_dir}/manifest.json"
amo_metadata_path="${firefox_dir}/amo/metadata.listed.json"
amo_icon_path="${firefox_dir}/icons/icon-128.png"

required_env=(
  WEB_EXT_API_KEY
  WEB_EXT_API_SECRET
)

for key in "${required_env[@]}"; do
  if [[ -z "${!key:-}" ]]; then
    echo "Missing required environment variable: ${key}" >&2
    exit 1
  fi
done

if ! command -v npx >/dev/null 2>&1; then
  echo "npx is required to deploy the Firefox extension package." >&2
  exit 1
fi

python_bin=""
if command -v python3 >/dev/null 2>&1; then
  python_bin="python3"
elif command -v python >/dev/null 2>&1; then
  python_bin="python"
else
  echo "python3 (or python) is required to deploy the Firefox extension package." >&2
  exit 1
fi

"${script_dir}/build.sh"

latest_zip="$(ls -t "${out_dir}"/myfyp-firefox-v*.zip | head -n 1)"
if [[ -z "${latest_zip:-}" ]]; then
  echo "No built package found in dist/extensions/firefox." >&2
  exit 1
fi

extension_version="$("${python_bin}" - "${manifest_path}" <<'PY'
import json
import sys

manifest_file = sys.argv[1]
with open(manifest_file, "r", encoding="utf-8") as handle:
    manifest = json.load(handle)

version = manifest.get("version")
if not isinstance(version, str) or not version.strip():
    raise SystemExit("manifest.json is missing a valid version string.")
print(version.strip())
PY
)"

amo_channel="${FIREFOX_AMO_CHANNEL:-unlisted}"
artifacts_dir="${out_dir}/signed"
mkdir -p "${artifacts_dir}"
rm -f "${artifacts_dir}"/*.xpi

web_ext_args=()
if [[ "${amo_channel}" == "listed" ]]; then
  if [[ ! -f "${amo_metadata_path}" ]]; then
    echo "Missing AMO metadata file for listed deployment: ${amo_metadata_path}" >&2
    exit 1
  fi
  web_ext_args+=(--amo-metadata "${amo_metadata_path}")
fi

echo "Uploading and signing Firefox extension package: ${latest_zip}"
npx --yes web-ext@8 sign \
  --source-dir "${firefox_dir}" \
  --artifacts-dir "${artifacts_dir}" \
  --api-key "${WEB_EXT_API_KEY}" \
  --api-secret "${WEB_EXT_API_SECRET}" \
  --channel "${amo_channel}" \
  --ignore-files "scripts/**" "README.md" \
  "${web_ext_args[@]}"

signed_source_xpi="$(ls -t "${artifacts_dir}"/*.xpi | head -n 1)"
if [[ -z "${signed_source_xpi:-}" ]]; then
  echo "web-ext sign did not produce any .xpi artifact." >&2
  exit 1
fi

versioned_xpi="${artifacts_dir}/myfyp-firefox-${extension_version}.xpi"
latest_xpi="${artifacts_dir}/myfyp-firefox-latest.xpi"

mv "${signed_source_xpi}" "${versioned_xpi}"
cp "${versioned_xpi}" "${latest_xpi}"

if [[ "${amo_channel}" == "listed" ]]; then
  if ! command -v curl >/dev/null 2>&1; then
    echo "curl is required to upload AMO listing icon for listed deployments." >&2
    exit 1
  fi
  if [[ ! -f "${amo_icon_path}" ]]; then
    echo "Missing AMO icon file: ${amo_icon_path}" >&2
    exit 1
  fi

  addon_id="$("${python_bin}" - "${manifest_path}" <<'PY'
import json
import sys

manifest_file = sys.argv[1]
with open(manifest_file, "r", encoding="utf-8") as handle:
    manifest = json.load(handle)

print(manifest["browser_specific_settings"]["gecko"]["id"])
PY
)"

  addon_id_encoded="$("${python_bin}" - "${addon_id}" <<'PY'
import sys
from urllib.parse import quote

print(quote(sys.argv[1], safe=""))
PY
)"

  amo_jwt="$("${python_bin}" - "${WEB_EXT_API_KEY}" "${WEB_EXT_API_SECRET}" <<'PY'
import base64
import hashlib
import hmac
import json
import time
import uuid
import sys

api_key = sys.argv[1]
api_secret = sys.argv[2]

header = {"alg": "HS256", "typ": "JWT"}
now = int(time.time())
payload = {
    "iss": api_key,
    "jti": str(uuid.uuid4()),
    "iat": now,
    "exp": now + 300,
}

def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")

header_b64 = b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
payload_b64 = b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
signature = hmac.new(api_secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
signature_b64 = b64url(signature)
print(f"{header_b64}.{payload_b64}.{signature_b64}")
PY
)"

  amo_icon_endpoint="https://addons.mozilla.org/api/v5/addons/addon/${addon_id_encoded}/"
  echo "Uploading AMO listing icon for ${addon_id}"
  curl -fsS -X PATCH \
    -H "Authorization: JWT ${amo_jwt}" \
    -F "icon=@${amo_icon_path};type=image/png" \
    "${amo_icon_endpoint}" >/dev/null
fi

echo "Signed Firefox extension artifacts written to: ${artifacts_dir}"
