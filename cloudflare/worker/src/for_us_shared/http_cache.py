from __future__ import annotations

from datetime import datetime, timezone

from for_us_shared.formatting import to_utc


def build_etag(prefix: str, snapshot_hash: str) -> str:
    return f'"{prefix}-{snapshot_hash}"'


def build_cache_headers(expires_at: datetime, etag: str) -> dict[str, str]:
    now = datetime.now(timezone.utc)
    max_age = max(0, int((to_utc(expires_at) - now).total_seconds()))
    return {
        "Cache-Control": f"public, max-age={max_age}, immutable",
        "ETag": etag,
    }


def if_none_match_matches(header_value: str | None, expected_etag: str) -> bool:
    if header_value is None:
        return False
    if header_value.strip() == "*":
        return True
    candidates = [token.strip() for token in header_value.split(",")]
    return expected_etag in candidates
