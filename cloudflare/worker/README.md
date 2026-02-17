# Cloudflare Worker (Reset)

This directory was intentionally reset to start over.

Next step: rebuild Cloudflare deployment by extracting reusable shared core logic from `api/src` and adding thin runtime adapters for:
- FastAPI + SQLite (`api`)
- Cloudflare Worker + D1 (`cloudflare/worker`)
