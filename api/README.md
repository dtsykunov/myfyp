# API Scaffold

This directory contains the initial API scaffold.

`for_us_api.rendering` delegates to shared HTML rendering in
`cloudflare/worker/src/for_us_shared/rendering.py` so API and Worker stay consistent.

## Endpoints

- `GET /health`
- `POST /api/snapshots`: validates and stores recommendation payload in SQLite, returns `hash` and `expiresAt`.
- `GET /api/snapshots/{hash}`: returns stored payload JSON for an active snapshot.
- `GET /{hash}`: renders a basic server-side HTML page for the snapshot.

## Abuse Controls (Defaults)

- `POST /api/snapshots` request body max size: 64 KB
- `videos` max items: 200
- `shorts` max items: 200
- Create rate limit: 10/min per IP
- Read rate limit: 120/min per IP
- Create daily quota: 200/day per IP
- Expired snapshot cleanup runs at startup and periodically during writes

## Local (Nix Flake)

```bash
nix develop --command sh -c "cd api && ./scripts/run-tests.sh"
nix develop --command sh -c "cd api && ./scripts/run-lint.sh"
nix develop --command sh -c "cd api && ./scripts/run-typecheck.sh"
nix develop --command sh -c "cd api && ./scripts/run-api.sh"
```

These scripts configure `PYTHONPATH` automatically for shared runtime imports.

## Docker (CI-aligned)

From repository root:

```bash
docker compose run --rm api-lint
docker compose run --rm api-typecheck
docker compose run --rm api-test
docker compose up api
```
