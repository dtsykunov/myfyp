# API Scaffold

This directory contains the initial API scaffold.

## Endpoints

- `GET /health`
- `POST /api/snapshots`: validates and stores recommendation payload in SQLite, returns `hash` and `expiresAt`.

## Local (Nix Flake)

```bash
nix develop --command sh -c "cd api && ./scripts/run-tests.sh"
nix develop --command sh -c "cd api && ./scripts/run-lint.sh"
nix develop --command sh -c "cd api && ./scripts/run-typecheck.sh"
nix develop --command sh -c "cd api && ./scripts/run-api.sh"
```

## Docker (CI-aligned)

From repository root:

```bash
docker compose run --rm api-lint
docker compose run --rm api-typecheck
docker compose run --rm api-test
docker compose up api
```
