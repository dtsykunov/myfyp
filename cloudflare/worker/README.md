# Cloudflare Worker (Python)

This Worker target contains a deployable shared runtime package in `src/for_us_shared`.

Shared runtime modules:
- Pydantic payload models (`for_us_shared.models`)
- ETag/cache helpers (`for_us_shared.http_cache`)
- HTML rendering (`for_us_shared.rendering`)

Runtime target:
- Python Worker packaging targets Python 3.13 with a Worker-compatible Pydantic runtime.

Adapter-specific code in this folder:
- Cloudflare request/response entrypoint (`src/entry.py`)
- D1 persistence and abuse-control adapters (`src/for_us_worker`)

## Local checks

```bash
nix develop --command sh -c "./cloudflare/worker/scripts/run-lint.sh"
nix develop --command sh -c "./cloudflare/worker/scripts/run-typecheck.sh"
nix develop --command sh -c "./cloudflare/worker/scripts/run-tests.sh"
```

## Local dev server

Run the Worker locally on `http://127.0.0.1:8787`:

```bash
nix develop --command sh -c "./cloudflare/worker/scripts/run-dev.sh"
```

## D1 migrations

```bash
npx wrangler d1 migrations apply myfyp --local
npx wrangler d1 migrations apply myfyp --remote
```

## GitHub Actions Deployment

`Deploy Worker` workflow applies D1 migrations and deploys the worker from CI.
It uses `pywrangler` (not plain `wrangler deploy`) so Python dependencies are bundled for deployment.

Use a protected GitHub environment named `production` and configure:

- Secrets:
  - `CLOUDFLARE_API_TOKEN`
  - `CLOUDFLARE_ACCOUNT_ID`
- Variables:
  - `CF_WORKER_NAME`
  - `CF_D1_DATABASE_NAME`
  - `CF_D1_DATABASE_ID`
  - `CF_ROUTE_PATTERN` (optional; set with `CF_ZONE_ID` for custom domain routing)
  - `CF_ZONE_ID` (optional; set with `CF_ROUTE_PATTERN`)

The workflow renders `cloudflare/worker/wrangler.production.toml` at runtime and never stores credentials in the repository.
