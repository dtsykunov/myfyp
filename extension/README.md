# Extension (MVP Userscript)

This folder contains the MVP browser-side component as a userscript.

Current state:
- A runnable userscript parses YouTube homepage cards into `videos` and `shorts`.
- It uploads snapshots to API endpoint `POST /api/snapshots` and logs API response in console.
- It does **not** auto-upload on page load. Upload happens only on explicit manual call.

## Current userscript output

From browser console on YouTube:

```js
window.myfyp.uploadLatestSnapshot()
```

This uploads payload JSON in the form:

```json
{
  "capturedAt": "<ISO timestamp>",
  "pageUrl": "https://www.youtube.com/",
  "videos": ["lzChIIJMpGk", "..."],
  "shorts": ["abc123XYZ78", "..."]
}
```

The API response is printed in console, for example:

```json
{
  "hash": "Ab12Cd34Ef56",
  "expiresAt": "2026-02-24T11:00:00Z"
}
```

## API URL configuration

Default API URL is `http://127.0.0.1:8000`.

To override it from console:

```js
window.myfyp.setApiBaseUrl("http://127.0.0.1:8000")
```

If `window.myfyp` is undefined, force-update the userscript in Tampermonkey and reload YouTube.

Planned behavior:
1. Parse recommendations from `youtube.com`.
2. Build a JSON payload.
3. Send payload to API.
4. Present generated share link to the user.
