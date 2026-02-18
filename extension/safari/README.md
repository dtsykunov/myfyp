# myfyp Safari Extension

Safari Web Extension package that mirrors the userscript behavior:

- Manual snapshot upload from YouTube home page.
- No automatic upload on page load.
- Link history toast with share/delete/remove controls.
- API base URL configuration.

## Run in Safari (local)

1. Generate an Xcode project:
   ```bash
   ./extension/safari/scripts/deploy.sh
   ```
2. Open the generated project in Xcode and run the app target.
3. Enable the extension in Safari extension settings.

## Usage

1. Open `https://www.youtube.com/` (or `https://m.youtube.com/`).
2. Open the extension popup.
3. Click `Upload Snapshot`.
4. View the result toast on the YouTube page.

## API base URL

Use the popup input to change API base URL (default: `https://myfyp.link`).

## Build package

```bash
./extension/safari/scripts/build.sh
```

This creates a zip file in `dist/extensions/safari/`.

## Convert/Deploy

```bash
./extension/safari/scripts/deploy.sh
```

The script converts the extension to an Xcode project on macOS. Optional archive/export
steps are enabled when signing variables are provided.
