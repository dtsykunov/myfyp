# myfyp Chrome Extension

Chrome Manifest V3 extension that mirrors the userscript behavior:

- Manual snapshot upload from YouTube home page.
- No automatic upload on page load.
- Built-in link history with share/delete/remove controls.

## Load unpacked (local)

1. Open `chrome://extensions`.
2. Enable **Developer mode**.
3. Click **Load unpacked**.
4. Select the `extension/chrome` directory.

## Usage

1. Open `https://www.youtube.com/` (or `https://m.youtube.com/`).
2. Open extension popup.
3. Click `Upload Snapshot`.
4. View created links directly in the popup.

## Build package

```bash
./extension/chrome/scripts/build.sh
```

This creates a zip file in `dist/extensions/chrome/`.

## Discovery Metadata Notes

- In-repo metadata comes from `extension/chrome/manifest.json` (name, short name, description, homepage, icons).
- Chrome Web Store listing metadata such as category, detailed description, screenshots, and promotional assets are managed in the Chrome Web Store dashboard.
