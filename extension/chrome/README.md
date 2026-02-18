# myfyp Chrome Extension

Chrome Manifest V3 extension that mirrors the userscript behavior:

- Manual snapshot upload from YouTube home page.
- No automatic upload on page load.
- Link history toast with share/delete/remove controls.
- API base URL configuration.

## Load unpacked (local)

1. Open `chrome://extensions`.
2. Enable **Developer mode**.
3. Click **Load unpacked**.
4. Select the `extension/chrome` directory.

## Usage

1. Open `https://www.youtube.com/` (or `https://m.youtube.com/`).
2. Open extension popup.
3. Click `Upload Snapshot`.
4. View the result toast on the YouTube page.

## API base URL

Use the popup input to change API base URL (default: `https://myfyp.link`).

## Build package

```bash
./extension/chrome/scripts/build.sh
```

This creates a zip file in `dist/extensions/chrome/`.
