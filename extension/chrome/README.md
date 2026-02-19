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

## Install from GitHub release (manual)

1. Download `myfyp-chrome-latest.zip` from:
   `https://github.com/dtsykunov/myfyp/releases/download/extensions-latest/myfyp-chrome-latest.zip`
2. Unzip the archive.
3. Open `chrome://extensions`.
4. Enable **Developer mode**.
5. Click **Load unpacked** and select the unzipped folder.

## Usage

1. Open extension popup on any page to review previously created links.
2. Open `https://www.youtube.com/` (or `https://m.youtube.com/`) homepage when you want a new upload.
3. Click `Upload Snapshot` in the popup.
4. View created links directly in the popup.

## Build package

```bash
./extension/chrome/scripts/build.sh
```

This creates a zip file in `dist/extensions/chrome/`.

## Publish to Chrome Web Store

Local publish command:

```bash
CHROME_WEBSTORE_CLIENT_ID=... \
CHROME_WEBSTORE_CLIENT_SECRET=... \
CHROME_WEBSTORE_REFRESH_TOKEN=... \
CHROME_WEBSTORE_EXTENSION_ID=... \
CHROME_WEBSTORE_PUBLISHER_ID=... \
./extension/chrome/scripts/deploy.sh
```

Optional:

```bash
CHROME_WEBSTORE_SKIP_PUBLISH=true ./extension/chrome/scripts/deploy.sh
```

This uploads a new draft but skips the publish step.

GitHub Actions workflow:

- `.github/workflows/deploy-extension-chrome-webstore.yml`
- trigger manually via **Actions -> Deploy Chrome Extension to Web Store -> Run workflow**
- required repository/environment secrets:
  - `CHROME_WEBSTORE_CLIENT_ID`
  - `CHROME_WEBSTORE_CLIENT_SECRET`
  - `CHROME_WEBSTORE_REFRESH_TOKEN`
  - `CHROME_WEBSTORE_EXTENSION_ID`
  - `CHROME_WEBSTORE_PUBLISHER_ID`

Where values come from:

- `CHROME_WEBSTORE_EXTENSION_ID`: extension item ID from Chrome Web Store Developer Dashboard.
- `CHROME_WEBSTORE_PUBLISHER_ID`: publisher ID from Chrome Web Store account details.
- `CHROME_WEBSTORE_CLIENT_ID` and `CHROME_WEBSTORE_CLIENT_SECRET`: OAuth client in Google Cloud project with Chrome Web Store API enabled.
- `CHROME_WEBSTORE_REFRESH_TOKEN`: OAuth refresh token for scope `https://www.googleapis.com/auth/chromewebstore`.

## Discovery Metadata Notes

- In-repo metadata comes from `extension/chrome/manifest.json` (name, short name, description, homepage, icons).
- Chrome Web Store listing metadata such as category, detailed description, screenshots, and promotional assets are managed in the Chrome Web Store dashboard.
