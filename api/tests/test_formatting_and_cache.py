from datetime import datetime, timedelta, timezone

from for_us_api.formatting import format_compact_views, format_relative_time, format_snapshot_taken_at
from for_us_api.http_cache import build_cache_headers, build_etag, if_none_match_matches


def test_build_etag_and_matching() -> None:
    etag = build_etag("api", "Ab12Cd34Ef56")
    assert etag == '"api-Ab12Cd34Ef56"'
    assert if_none_match_matches(etag, etag)
    assert if_none_match_matches('"other", "api-Ab12Cd34Ef56"', etag)
    assert not if_none_match_matches('"other"', etag)


def test_build_cache_headers_contains_expected_values() -> None:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    headers = build_cache_headers(expires_at, '"api-Ab12Cd34Ef56"')
    assert headers["ETag"] == '"api-Ab12Cd34Ef56"'
    assert headers["Cache-Control"].startswith("public, max-age=")


def test_format_snapshot_taken_at() -> None:
    taken_at = datetime(2026, 2, 17, 11, 0, 0, tzinfo=timezone.utc)
    assert format_snapshot_taken_at(taken_at) == "2026-02-17 11:00:00 UTC"


def test_format_relative_time_and_compact_views() -> None:
    reference_time = datetime(2026, 2, 17, 12, 0, 0, tzinfo=timezone.utc)
    published_at = datetime(2026, 2, 17, 11, 0, 0, tzinfo=timezone.utc)
    assert format_relative_time(published_at, reference_time) == "1 hour ago"
    assert format_compact_views(437) == "437 views"
    assert format_compact_views(35_000) == "35K views"
    assert format_compact_views(1_500_000) == "1.5M views"
