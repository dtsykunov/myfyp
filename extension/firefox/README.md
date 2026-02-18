# myfyp Firefox Extension

Firefox WebExtension that mirrors the userscript behavior:

- Manual snapshot upload from YouTube home page.
- No automatic upload on page load.
- Built-in link history with share/delete/remove controls.

## Load temporary add-on (local)

1. Open `about:debugging#/runtime/this-firefox`.
2. Click **Load Temporary Add-on…**.
3. Select `extension/firefox/manifest.json`.

## Usage

1. Open `https://www.youtube.com/` (or `https://m.youtube.com/`).
2. Open the extension popup.
3. Click `Upload Snapshot`.
4. View created links directly in the popup.

## Build package

```bash
./extension/firefox/scripts/build.sh
```

This creates a zip file in `dist/extensions/firefox/`.

## Deploy to AMO

```bash
WEB_EXT_API_KEY=... \
WEB_EXT_API_SECRET=... \
./extension/firefox/scripts/deploy.sh
```

For `listed` channel deployments, AMO listing metadata is sourced from:

- `extension/firefox/amo/metadata.listed.json` (summary, categories, tags, support/homepage links)
- `extension/firefox/icons/icon-128.png` (listing icon upload)

## GitHub Actions Deployment

Workflow: `.github/workflows/deploy-extension-firefox.yml`

Required repository secrets:
- `FIREFOX_AMO_API_KEY` - AMO JWT issuer/API key.
- `FIREFOX_AMO_API_SECRET` - AMO JWT secret.

Workflow input:
- `amo_channel` - `unlisted` (default) or `listed`.

Workflow output:
- uploads signed `.xpi` and build artifacts
- publishes signed `.xpi` to GitHub Release tag `extensions-latest`
