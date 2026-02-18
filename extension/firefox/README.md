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
