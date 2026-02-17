# Cloudflare Worker (Python)

This Worker target contains a deployable shared runtime package in `src/for_us_shared`.

Shared runtime modules:
- Pydantic payload models (`for_us_shared.models`)
- ETag/cache helpers (`for_us_shared.http_cache`)
- HTML rendering (`for_us_shared.rendering`)

Adapter-specific code in this folder:
- Cloudflare request/response entrypoint (`src/entry.py`)
- D1 persistence and abuse-control adapters (`src/for_us_worker`)

## Local checks

```bash
nix develop --command sh -c "./cloudflare/worker/scripts/run-lint.sh"
nix develop --command sh -c "./cloudflare/worker/scripts/run-typecheck.sh"
nix develop --command sh -c "./cloudflare/worker/scripts/run-tests.sh"
```

## D1 migrations

```bash
npx wrangler d1 migrations apply for-us-page --local
npx wrangler d1 migrations apply for-us-page --remote
```
