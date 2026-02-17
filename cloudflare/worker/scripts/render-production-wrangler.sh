#!/usr/bin/env sh
set -eu

output_file="${1:-cloudflare/worker/wrangler.production.toml}"

: "${CF_WORKER_NAME:?CF_WORKER_NAME is required}"
: "${CF_D1_DATABASE_NAME:?CF_D1_DATABASE_NAME is required}"
: "${CF_D1_DATABASE_ID:?CF_D1_DATABASE_ID is required}"

workers_dev="true"
if [ -n "${CF_ROUTE_PATTERN:-}" ] || [ -n "${CF_ZONE_ID:-}" ]; then
  : "${CF_ROUTE_PATTERN:?CF_ROUTE_PATTERN must be set when CF_ZONE_ID is set}"
  : "${CF_ZONE_ID:?CF_ZONE_ID must be set when CF_ROUTE_PATTERN is set}"
  workers_dev="false"
fi

{
  cat <<EOT
name = "${CF_WORKER_NAME}"
main = "src/entry.py"
compatibility_date = "2026-02-17"
compatibility_flags = ["python_workers"]
workers_dev = ${workers_dev}
EOT

  if [ "${workers_dev}" = "false" ]; then
    cat <<EOT

routes = [
  { pattern = "${CF_ROUTE_PATTERN}", zone_id = "${CF_ZONE_ID}" }
]
EOT
  fi

  cat <<EOT

[[d1_databases]]
binding = "DB"
database_name = "${CF_D1_DATABASE_NAME}"
database_id = "${CF_D1_DATABASE_ID}"

[triggers]
crons = ["0 * * * *"]

[observability.logs]
enabled = true
EOT
} > "${output_file}"
