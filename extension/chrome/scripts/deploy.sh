#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../../.." && pwd)"

required_env=(
  CHROME_WEBSTORE_CLIENT_ID
  CHROME_WEBSTORE_CLIENT_SECRET
  CHROME_WEBSTORE_REFRESH_TOKEN
  CHROME_WEBSTORE_EXTENSION_ID
  CHROME_WEBSTORE_PUBLISHER_ID
)

for key in "${required_env[@]}"; do
  if [[ -z "${!key:-}" ]]; then
    echo "Missing required environment variable: ${key}" >&2
    exit 1
  fi
done

python_bin=""
if command -v python3 >/dev/null 2>&1; then
  python_bin="python3"
elif command -v python >/dev/null 2>&1; then
  python_bin="python"
else
  echo "python3 (or python) is required to deploy the Chrome extension package." >&2
  exit 1
fi

skip_publish="${CHROME_WEBSTORE_SKIP_PUBLISH:-false}"
skip_publish="$(printf '%s' "${skip_publish}" | tr '[:upper:]' '[:lower:]')"
if [[ "${skip_publish}" != "true" && "${skip_publish}" != "false" ]]; then
  echo "CHROME_WEBSTORE_SKIP_PUBLISH must be true or false." >&2
  exit 1
fi

"${script_dir}/build.sh"

latest_zip="$(ls -t "${repo_root}/dist/extensions/chrome"/myfyp-chrome-v*.zip | head -n 1)"
if [[ -z "${latest_zip}" ]]; then
  echo "No built package found in dist/extensions/chrome." >&2
  exit 1
fi

echo "Uploading package: ${latest_zip}"

oauth_body_file="$(mktemp)"
oauth_status="$(
  curl -sS -o "${oauth_body_file}" -w "%{http_code}" -X POST "https://oauth2.googleapis.com/token" \
    --data-urlencode "client_id=${CHROME_WEBSTORE_CLIENT_ID}" \
    --data-urlencode "client_secret=${CHROME_WEBSTORE_CLIENT_SECRET}" \
    --data-urlencode "refresh_token=${CHROME_WEBSTORE_REFRESH_TOKEN}" \
    --data-urlencode "grant_type=refresh_token"
)"
oauth_response="$(cat "${oauth_body_file}")"
rm -f "${oauth_body_file}"

access_token="$("${python_bin}" - <<'PY' "${oauth_status}" "${oauth_response}"
from __future__ import annotations

import json
import sys

status_code = int(sys.argv[1])
raw_response = sys.argv[2]

try:
    payload = json.loads(raw_response) if raw_response.strip() else {}
except json.JSONDecodeError:
    payload = {}

if not (200 <= status_code < 300):
    error_code = ""
    error_description = ""
    if isinstance(payload, dict):
        error_code = str(payload.get("error") or "")
        error_description = str(payload.get("error_description") or "")
    detail = error_code or "oauth_token_request_failed"
    if error_description:
        detail = f"{detail}: {error_description}"
    raise SystemExit(
        f"OAuth token exchange failed ({status_code}). "
        f"{detail}. Verify client ID/secret, refresh token, and OAuth consent status."
    )

access_token = payload.get("access_token") if isinstance(payload, dict) else None
if not isinstance(access_token, str) or not access_token:
    raise SystemExit("OAuth token exchange succeeded but access_token was missing in response.")
print(access_token)
PY
)"

upload_body_file="$(mktemp)"
upload_status="$(
  curl -sS -o "${upload_body_file}" -w "%{http_code}" -X POST \
    -H "Authorization: Bearer ${access_token}" \
    -H "Content-Type: application/zip" \
    --data-binary @"${latest_zip}" \
    "https://chromewebstore.googleapis.com/upload/v2/publishers/${CHROME_WEBSTORE_PUBLISHER_ID}/items/${CHROME_WEBSTORE_EXTENSION_ID}:upload"
)"
upload_response="$(cat "${upload_body_file}")"
rm -f "${upload_body_file}"

"${python_bin}" - <<'PY' "${upload_status}" "${upload_response}"
from __future__ import annotations

import json
import sys

status_code = int(sys.argv[1])
raw_response = sys.argv[2]

try:
    payload = json.loads(raw_response) if raw_response.strip() else {}
except json.JSONDecodeError:
    payload = {"raw": raw_response}

if 200 <= status_code < 300:
    print("Chrome Web Store upload succeeded.")
    raise SystemExit(0)

details = ""
if isinstance(payload, dict):
    details = json.dumps(payload)

if status_code == 409:
    version_message = details.lower()
    if "already exists" in version_message:
        print("Chrome Web Store upload skipped: this version is already uploaded.")
        raise SystemExit(0)

raise SystemExit(f"Chrome Web Store upload failed ({status_code}): {details or raw_response}")
PY

if [[ "${skip_publish}" == "true" ]]; then
  echo "Skipping publish step (CHROME_WEBSTORE_SKIP_PUBLISH=true)."
  exit 0
fi

publish_body_file="$(mktemp)"
publish_status="$(
  curl -sS -o "${publish_body_file}" -w "%{http_code}" -X POST \
    -H "Authorization: Bearer ${access_token}" \
    -H "Content-Type: application/json" \
    --data '{}' \
    "https://chromewebstore.googleapis.com/v2/publishers/${CHROME_WEBSTORE_PUBLISHER_ID}/items/${CHROME_WEBSTORE_EXTENSION_ID}/publish"
)"
publish_response="$(cat "${publish_body_file}")"
rm -f "${publish_body_file}"

"${python_bin}" - <<'PY' "${publish_status}" "${publish_response}"
from __future__ import annotations

import json
import sys

status_code = int(sys.argv[1])
raw_response = sys.argv[2]

try:
    payload = json.loads(raw_response) if raw_response.strip() else {}
except json.JSONDecodeError:
    payload = {"raw": raw_response}

if 200 <= status_code < 300:
    print(f"Chrome Web Store publish succeeded: {json.dumps(payload)}")
    raise SystemExit(0)

details = json.dumps(payload) if isinstance(payload, dict) else raw_response
if status_code == 409 and "already" in details.lower():
    print("Chrome Web Store publish skipped: current version is already published.")
    raise SystemExit(0)

raise SystemExit(f"Chrome Web Store publish failed ({status_code}): {details}")
PY
