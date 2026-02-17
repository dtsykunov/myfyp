# Cloudflare Worker (Python)

This Worker target reuses Python logic from `api/src/for_us_api`.

Current reuse:
- Pydantic payload models (`for_us_api.models`)
- ETag/cache helpers (`for_us_api.http_cache`)
- HTML rendering (`for_us_api.rendering`)

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
