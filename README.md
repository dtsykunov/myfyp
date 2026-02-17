# For Us Page

`For Us Page` is a web service for sharing your current YouTube recommendations through a temporary link.

## Purpose

YouTube recommendations are personal and constantly changing.  
This project lets a user capture their current YouTube home feed and share it with someone else as a simple URL.

## User Flow

1. Install the browser extension.
2. Open YouTube.
3. Click `Share Recommendation Page` in the extension.
4. The extension generates a share link: `https://<domain>/<hash>`.
5. Anyone with that link can open a rendered page of the captured recommendations.

## System Flow (Under the Hood)

1. The extension parses the user's YouTube home page.
2. It builds a JSON payload containing recommended video links (and related metadata, if available).
3. The payload is sent to the backend API.
4. The API stores the payload in SQLite and returns a unique `hash`.
5. A request to `/<hash>` retrieves the stored payload and renders it as a plain HTML page.

## Data Retention

- Share links are temporary.
- Stored recommendation data expires after **7 days**.
- Expired records are deleted.

## Tech Stack

- **Backend API:** Python + FastAPI
- **Database:** SQLite
- **Rendered page:** Plain HTML

## Notes for Contributors / AI Agents

- Primary goal: fast, simple sharing of a YouTube recommendation snapshot.
- Architecture is intentionally minimal: extension -> API -> SQLite -> HTML page.
- Privacy/retention behavior (7-day expiration) is a core product rule and should be preserved.
