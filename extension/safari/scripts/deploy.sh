#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
safari_dir="$(cd "${script_dir}/.." && pwd)"
repo_root="$(cd "${script_dir}/../../.." && pwd)"
out_dir="${repo_root}/dist/extensions/safari"
project_dir="${out_dir}/xcode"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Safari deployment requires macOS with Xcode Command Line Tools installed." >&2
  exit 1
fi

if ! command -v xcrun >/dev/null 2>&1; then
  echo "xcrun is required for Safari extension conversion/deployment." >&2
  exit 1
fi

"${script_dir}/build.sh"

app_name="${SAFARI_APP_NAME:-myfyp}"
bundle_identifier="${SAFARI_BUNDLE_IDENTIFIER:-com.myfyp.extension}"

mkdir -p "${project_dir}"

xcrun safari-web-extension-converter "${safari_dir}" \
  --project-location "${project_dir}" \
  --app-name "${app_name}" \
  --bundle-identifier "${bundle_identifier}" \
  --no-open \
  --force

echo "Safari Xcode project generated at: ${project_dir}"

if [[ "${SAFARI_DEPLOY_SKIP_ARCHIVE:-1}" == "1" ]]; then
  echo "Skipping archive/upload (set SAFARI_DEPLOY_SKIP_ARCHIVE=0 to continue)."
  exit 0
fi

required_env=(
  APPLE_DEVELOPMENT_TEAM
  SAFARI_EXPORT_OPTIONS_PLIST
)

for key in "${required_env[@]}"; do
  if [[ -z "${!key:-}" ]]; then
    echo "Missing required environment variable for archive/export: ${key}" >&2
    exit 1
  fi
done

project_path="${project_dir}/${app_name}.xcodeproj"
archive_path="${out_dir}/${app_name}.xcarchive"
export_path="${out_dir}/export"

xcodebuild \
  -project "${project_path}" \
  -scheme "${app_name}" \
  -configuration Release \
  -archivePath "${archive_path}" \
  DEVELOPMENT_TEAM="${APPLE_DEVELOPMENT_TEAM}" \
  CODE_SIGN_STYLE=Automatic \
  archive

xcodebuild \
  -exportArchive \
  -archivePath "${archive_path}" \
  -exportPath "${export_path}" \
  -exportOptionsPlist "${SAFARI_EXPORT_OPTIONS_PLIST}"

echo "Safari extension export generated at: ${export_path}"
