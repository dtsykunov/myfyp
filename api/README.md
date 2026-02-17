# API Scaffold

This directory contains the initial API scaffold.

## Local (Nix Flake)

```bash
nix develop --command sh -c "cd api && ./scripts/run-tests.sh"
nix develop --command sh -c "cd api && ./scripts/run-lint.sh"
nix develop --command sh -c "cd api && ./scripts/run-api.sh"
```

## Docker (CI-aligned)

From repository root:

```bash
docker compose run --rm api-lint
docker compose run --rm api-test
docker compose up api
```
