# myfyp

`myfyp` lets you capture your current YouTube home recommendations and share them as a temporary link.

The project has two isolated parts:
- a userscript/browser extension (browser-side parser/uploader)
- a Python Cloudflare Worker (API + HTML rendering + D1 persistence)

## What It Does

1. You open YouTube Home.
2. You trigger upload manually from the userscript or extension UI.
3. The client parses recommendation cards and sends a JSON payload to the Worker API.
4. The Worker stores the snapshot for 7 days and returns:
   - share URL
   - remove URL
5. Anyone with the share link can open a rendered snapshot page.

## Current Status

- Userscript parsing is implemented.
- Browser extensions are implemented (Chrome + Firefox packages).
- Worker storage and rendering are implemented.
- Remove-by-token endpoint is implemented.
- Privacy page is implemented.
- Cloudflare Worker + D1 deployment path is implemented.

## Quick Start (Local)

1. Enter dev shell:
```bash
nix develop
```

2. Run local Worker server:
```bash
./cloudflare/worker/scripts/run-dev.sh
```

3. Install userscript in Tampermonkey from:
`https://raw.githubusercontent.com/dtsykunov/myfyp/master/extension/userscript/myfyp.user.js`

4. Open:
`https://www.youtube.com/`

5. Point userscript to local Worker once:
```js
window.myfyp.setApiBaseUrl("http://127.0.0.1:8787")
```

6. Trigger upload:
- userscript menu: `myfyp: Upload Snapshot`
- or console: `window.myfyp.uploadLatestSnapshot()`

## Data Model

`POST /api/snapshots` accepts:

```json
{
  "capturedAt": "2026-02-18T09:26:21Z",
  "pageUrl": "https://www.youtube.com/",
  "videos": [
    {
      "videoHash": "lzChIIJMpGk",
      "title": "deadlock: items for idiot",
      "channelName": "chalant",
      "channelLink": "https://www.youtube.com/@itschalant",
      "channelAvatar": "https://yt3.ggpht.com/example=s68-c-k-c0x00ffffff-no-rj",
      "viewCount": 81000,
      "publishedAt": "2026-02-15T09:26:21Z"
    }
  ],
  "shorts": [
    {
      "videoHash": "1rInJtz8QWg",
      "title": "DEAD DADS | Dan Soder",
      "viewCount": 32000
    }
  ]
}
```

Compatibility note: `videos` and `shorts` also accept hash-only entries (`["abc123..."]`), which are normalized server-side.

Create response example:

```json
{
  "hash": "Ab12Cd34Ef56",
  "expiresAt": "2026-02-25T09:26:21Z",
  "removeToken": "token-value",
  "url": "https://myfyp.link/Ab12Cd34Ef56",
  "removeUrl": "https://myfyp.link/api/snapshots/Ab12Cd34Ef56/remove/token-value"
}
```

## HTTP Endpoints

- `GET /health` - health check.
- `GET /` - home page with install/usage instructions.
- `GET /privacy` - privacy notice.
- `POST /api/snapshots` - create snapshot.
- `GET /api/snapshots/{hash}` - get stored payload JSON.
- `GET /{hash}` - render snapshot HTML.
- `GET /api/snapshots/{hash}/remove/{removeToken}` - delete snapshot by token.

## Retention and Abuse Controls

- Snapshot retention: 7 days.
- Expired snapshots are deleted automatically.

Default limits:
- max `videos`: 200
- max `shorts`: 200
- max request body: 64 KB
- create rate limit: 10/min/IP
- read rate limit: 120/min/IP
- create quota: 200/day/IP

## Userscript Notes

- Match scope is homepage-only:
  - `https://www.youtube.com/`
  - `https://m.youtube.com/`
- Upload is manual only (no auto-upload on page load).
- Ads are filtered out during parsing.
- Script keeps local history of created share/remove links (`localStorage`).

Console API:
- `window.myfyp.uploadLatestSnapshot()`
- `window.myfyp.showLinkHistory()`
- `window.myfyp.getLinkHistory()`
- `window.myfyp.setApiBaseUrl("http://127.0.0.1:8787")`
- `window.myfyp.getApiBaseUrl()`

## Repository Layout

- `extension/userscript/myfyp.user.js` - Tampermonkey userscript.
- `extension/chrome/` - Chrome extension source/build scripts.
- `extension/firefox/` - Firefox extension source/build scripts.
- `cloudflare/worker/` - Python Worker + D1 implementation.
- `cloudflare/worker/src/for_us_shared/` - shared backend runtime (models, abuse helpers, formatting, rendering).
- `brand/logo-mark.svg` - master square logo source.
- `brand/icons/web/` - website favicon assets (`png`, `svg`, `ico`).
- `extension/chrome/icons/` - Chrome extension icons.
- `extension/firefox/icons/` - Firefox extension icons.
- `docker-compose.yml` - containerized worker lint/typecheck/test/dev server.
- `flake.nix` - local reproducible dev shell.
- `.github/workflows/ci.yml` - Docker-based quality checks.
- `.github/workflows/deploy-worker.yml` - Worker deploy + D1 migrations.
- `.github/workflows/deploy-extension-firefox.yml` - Firefox AMO publish workflow.

Image binaries are tracked with Git LFS.

## Development Commands

Local (Nix):
```bash
nix develop --command sh -c "./cloudflare/worker/scripts/run-lint.sh"
nix develop --command sh -c "./cloudflare/worker/scripts/run-typecheck.sh"
nix develop --command sh -c "./cloudflare/worker/scripts/run-tests.sh"
nix develop --command sh -c "./cloudflare/worker/scripts/run-dev.sh"
```

CI-aligned (Docker):
```bash
docker compose run --rm worker-lint
docker compose run --rm worker-typecheck
docker compose run --rm worker-test
docker compose up worker
```

## Production Deployment (Cloudflare)

`Deploy Worker` workflow:
- runs after `CI` succeeds on `main`/`master` (or by manual dispatch)
- applies D1 migrations
- deploys worker using `pywrangler`

Required GitHub environment configuration is documented in:
`cloudflare/worker/README.md`

## Firefox Extension Deployment

`Deploy Firefox Extension` workflow:
- builds Firefox extension package
- submits/signs via AMO (`web-ext sign`)
- uploads built and signed artifacts as workflow artifacts (7-day retention)

Required GitHub repository secrets:
- `FIREFOX_AMO_API_KEY`
- `FIREFOX_AMO_API_SECRET`
