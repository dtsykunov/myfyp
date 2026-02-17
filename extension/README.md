# Extension (MVP Userscript)

This folder contains the MVP browser-side component as a userscript.

Current state:
- A runnable userscript exists and can parse YouTube homepage cards into video hashes.
- API integration is intentionally not implemented yet.

## Current userscript output

From browser console on YouTube:

```js
window.forUsPage.logSnapshot()
```

This returns JSON in the form:

```json
{
  "capturedAt": "<ISO timestamp>",
  "pageUrl": "https://www.youtube.com/",
  "videos": ["lzChIIJMpGk", "..."],
  "shorts": ["abc123XYZ78", "..."]
}
```

Planned behavior:
1. Parse recommendations from `youtube.com`.
2. Build a JSON payload.
3. Send payload to API.
4. Present generated share link to the user.
