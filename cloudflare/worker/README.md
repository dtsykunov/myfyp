# Cloudflare Worker (Python)

This Worker target reuses Python logic from `api/src/for_us_api`.

Current reuse:
- Pydantic payload models (`for_us_api.models`)
- ETag/cache helpers (`for_us_api.http_cache`)
- HTML rendering (`for_us_api.rendering`)

Adapter-specific code in this folder:
- Cloudflare request/response entrypoint
- D1 persistence adapter
