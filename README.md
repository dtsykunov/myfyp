# For Us Page

`For Us Page` is a web service for sharing your current YouTube recommendations through a temporary link.

## Purpose

YouTube recommendations are personal and constantly changing.  
This project lets a user capture their current YouTube home feed and share it with someone else as a simple URL.

## User Flow

1. Install the browser extension.
2. Open YouTube.
3. Click `Share Recommendation Page` in the extension.
4. The extension generates a share link: `https://<domain>/<hash>`.
5. Anyone with that link can open a rendered page of the captured recommendations.

## System Flow (Under the Hood)

1. The extension parses the user's YouTube home page.
2. It builds a JSON payload containing recommended video links (and related metadata, if available).
3. The payload is sent to the backend API.
4. The API stores the payload in SQLite and returns a unique `hash`.
5. A request to `/<hash>` retrieves the stored payload and renders it as a plain HTML page.

## Data Retention

- Share links are temporary.
- Stored recommendation data expires after **7 days**.
- Expired records are deleted.

## Tech Stack

- **Backend API:** Python + FastAPI
- **Database:** SQLite
- **Rendered page:** Plain HTML
- **MVP browser component:** Userscript (initial scaffold)

## Repository Layout

- `extension/`: browser-side MVP userscript scaffold.
- `api/`: Python/FastAPI service scaffold with tests.
- `flake.nix`: Nix flake dev shell for local reproducible runs.
- `.github/workflows/ci.yml`: CI that runs API tests via Docker.
- `docker-compose.yml`: local container workflow for run/test parity.

## Current Scaffold Status

- Extension:
  - Userscript shell exists (`extension/userscript/for-us-page.user.js`).
  - YouTube parsing + API upload behavior are TODO.
- API:
  - FastAPI app scaffold exists with `GET /health`.
  - Typed request/response/domain models are defined for snapshot payloads.
  - `POST /api/snapshots` stores payload in SQLite and returns share hash + expiry.
  - `GET /api/snapshots/{hash}` retrieves stored payload.
  - `GET /{hash}` renders a basic server-side HTML page for sharing.
  - Pyproject-based packaging, lint, strict type-checking, and pytest setup are configured.
  - Baseline tests validate API boot and model validation rules.

## API Create Snapshot (Implemented)

`POST /api/snapshots`

Example request body:

```json
{
  "capturedAt": "2026-02-17T11:00:00Z",
  "pageUrl": "https://www.youtube.com/",
  "videos": ["lzChIIJMpGk"],
  "shorts": ["dQw4w9WgXcQ"]
}
```

Example response:

```json
{
  "hash": "Ab12Cd34Ef56",
  "expiresAt": "2026-02-24T11:00:00Z"
}
```

`GET /api/snapshots/{hash}` returns the stored payload JSON.

`GET /{hash}` returns a minimal rendered HTML page listing videos and shorts.

## Run and Test

### Local (Nix Flake)

```bash
nix develop --command sh -c "cd api && ./scripts/run-tests.sh"
nix develop --command sh -c "cd api && ./scripts/run-lint.sh"
nix develop --command sh -c "cd api && ./scripts/run-typecheck.sh"
nix develop --command sh -c "cd api && ./scripts/run-api.sh"
```

### CI Path / Container Path (Docker)

```bash
docker compose run --rm api-lint
docker compose run --rm api-typecheck
docker compose run --rm api-test
docker compose up api
```

## Notes for Contributors / AI Agents

- Primary goal: fast, simple sharing of a YouTube recommendation snapshot.
- Architecture is intentionally minimal: extension -> API -> SQLite -> HTML page.
- Privacy/retention behavior (7-day expiration) is a core product rule and should be preserved.
