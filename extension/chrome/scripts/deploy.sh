#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../../.." && pwd)"

required_env=(
  CHROME_WEBSTORE_CLIENT_ID
  CHROME_WEBSTORE_CLIENT_SECRET
  CHROME_WEBSTORE_REFRESH_TOKEN
  CHROME_WEBSTORE_EXTENSION_ID
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

publish_target="${CHROME_WEBSTORE_PUBLISH_TARGET:-default}"

"${script_dir}/build.sh"

latest_zip="$(ls -t "${repo_root}/dist/extensions/chrome"/myfyp-chrome-v*.zip | head -n 1)"
if [[ -z "${latest_zip}" ]]; then
  echo "No built package found in dist/extensions/chrome." >&2
  exit 1
fi

echo "Uploading package: ${latest_zip}"

oauth_response="$(curl -fsS -X POST "https://oauth2.googleapis.com/token" \
  --data-urlencode "client_id=${CHROME_WEBSTORE_CLIENT_ID}" \
  --data-urlencode "client_secret=${CHROME_WEBSTORE_CLIENT_SECRET}" \
  --data-urlencode "refresh_token=${CHROME_WEBSTORE_REFRESH_TOKEN}" \
  --data-urlencode "grant_type=refresh_token")"

access_token="$("${python_bin}" - <<'PY' "${oauth_response}"
from __future__ import annotations

import json
import sys

payload = json.loads(sys.argv[1])
access_token = payload.get("access_token")
if not isinstance(access_token, str) or not access_token:
    raise SystemExit("Unable to acquire OAuth access token for Chrome Web Store API.")
print(access_token)
PY
)"

upload_response="$(curl -fsS -X PUT \
  -H "Authorization: Bearer ${access_token}" \
  -H "x-goog-api-version: 2" \
  -H "Content-Type: application/zip" \
  --data-binary @"${latest_zip}" \
  "https://www.googleapis.com/upload/chromewebstore/v1.1/items/${CHROME_WEBSTORE_EXTENSION_ID}")"

"${python_bin}" - <<'PY' "${upload_response}"
from __future__ import annotations

import json
import sys

payload = json.loads(sys.argv[1])
state = payload.get("uploadState")
if state not in {"SUCCESS", "OK"}:
    raise SystemExit(f"Chrome Web Store upload failed: {payload}")
print(f"Chrome Web Store upload succeeded: {state}")
PY

publish_url="https://www.googleapis.com/chromewebstore/v1.1/items/${CHROME_WEBSTORE_EXTENSION_ID}/publish?publishTarget=${publish_target}"
publish_response="$(curl -fsS -X POST \
  -H "Authorization: Bearer ${access_token}" \
  -H "x-goog-api-version: 2" \
  "${publish_url}")"

"${python_bin}" - <<'PY' "${publish_response}"
from __future__ import annotations

import json
import sys

payload = json.loads(sys.argv[1])
status = payload.get("status")
if isinstance(status, list):
    statuses = {str(item) for item in status}
else:
    statuses = {str(status)}
if not ({"OK", "ITEM_PENDING_REVIEW", "SUCCESS"} & statuses):
    raise SystemExit(f"Chrome Web Store publish failed: {payload}")
print(f"Chrome Web Store publish response: {payload}")
PY
