# Browser Integrations

This directory contains browser-side upload clients for myfyp:

- `userscript/`: Tampermonkey/Greasemonkey userscript (`myfyp.user.js`)
- `chrome/`: Chrome Manifest V3 extension
- `firefox/`: Firefox WebExtension
- `safari/`: Safari Web Extension package

All clients share the same behavior:

- Parse YouTube homepage recommendations into `videos` and `shorts`.
- Omit ad cards.
- Upload snapshots to `POST /api/snapshots`.
- Show toast feedback with share/remove links.
- Keep local history of created links.
- Trigger actions manually (no auto-upload on page load).

## Userscript quick commands

On `https://www.youtube.com/`:

```js
window.myfyp.uploadLatestSnapshot()
window.myfyp.showLinkHistory()
window.myfyp.setApiBaseUrl("https://myfyp.link")
```

## Build extension packages

```bash
./extension/chrome/scripts/build.sh
./extension/firefox/scripts/build.sh
./extension/safari/scripts/build.sh
```

Packages are written to `dist/extensions/<browser>/`.
