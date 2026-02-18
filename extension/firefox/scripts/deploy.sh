#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../../.." && pwd)"
firefox_dir="$(cd "${script_dir}/.." && pwd)"
out_dir="${repo_root}/dist/extensions/firefox"

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

"${script_dir}/build.sh"

latest_zip="$(ls -t "${out_dir}"/myfyp-firefox-v*.zip | head -n 1)"
if [[ -z "${latest_zip:-}" ]]; then
  echo "No built package found in dist/extensions/firefox." >&2
  exit 1
fi

amo_channel="${FIREFOX_AMO_CHANNEL:-unlisted}"
artifacts_dir="${out_dir}/signed"
mkdir -p "${artifacts_dir}"

echo "Uploading and signing Firefox extension package: ${latest_zip}"
npx --yes web-ext@8 sign \
  --source-dir "${firefox_dir}" \
  --artifacts-dir "${artifacts_dir}" \
  --api-key "${WEB_EXT_API_KEY}" \
  --api-secret "${WEB_EXT_API_SECRET}" \
  --channel "${amo_channel}" \
  --ignore-files "scripts/**" "README.md"

echo "Signed Firefox extension artifacts written to: ${artifacts_dir}"
