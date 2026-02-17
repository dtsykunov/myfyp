# pyright: reportPrivateUsage=false, reportDeprecated=false

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import cast

import pytest
try:
    from pydantic.v1 import ValidationError as PydanticValidationError
except ImportError:  # pragma: no cover
    from pydantic import ValidationError as PydanticValidationError

from for_us_shared import abuse, formatting, rendering
from for_us_shared.http_cache import build_cache_headers, build_etag, if_none_match_matches
from for_us_shared.models import (
    CreateSnapshotRequest,
    CreateSnapshotResponse,
    RecommendationItem,
    RecommendationPayload,
    StoredSnapshot,
    model_to_json_dict,
    parse_create_snapshot_request_json,
)


def _sample_payload() -> CreateSnapshotRequest:
    return CreateSnapshotRequest.parse_obj(
        {
            "capturedAt": "2026-02-17T11:00:00Z",
            "videos": [{"videoHash": "lzChIIJMpGk", "title": "Video"}],
            "shorts": [],
        }
    )


def test_shared_abuse_config_and_limiters() -> None:
    with pytest.raises(ValueError):
        abuse.AbuseConfig(max_snapshot_body_bytes=0)
    with pytest.raises(ValueError):
        abuse.AbuseConfig(post_requests_per_minute=0)
    with pytest.raises(ValueError):
        abuse.AbuseConfig(read_requests_per_minute=0)
    with pytest.raises(ValueError):
        abuse.AbuseConfig(write_quota_per_day_per_ip=0)

    times = iter([0.0, 1.0, 61.0])
    limiter = abuse._FixedWindowLimiter(limit=1, window_seconds=60, time_provider=lambda: next(times))
    assert limiter.allow("ip") is True
    assert limiter.allow("ip") is False
    assert limiter.allow("ip") is True

    days = iter([date(2026, 2, 17), date(2026, 2, 17), date(2026, 2, 18)])
    quota = abuse._DailyQuotaLimiter(limit=1, date_provider=lambda: next(days))
    assert quota.allow("ip") is True
    assert quota.allow("ip") is False
    assert quota.allow("ip") is True



def test_shared_guard_limits_create_and_read() -> None:
    cfg = abuse.AbuseConfig(
        post_requests_per_minute=2,
        read_requests_per_minute=1,
        write_quota_per_day_per_ip=1,
    )
    guard = abuse.InMemoryAbuseGuard(config=cfg)

    assert guard.allow_snapshot_create("198.51.100.1") == (True, "")
    assert guard.allow_snapshot_create("198.51.100.1") == (
        False,
        "Daily snapshot creation quota exceeded.",
    )

    limited_cfg = abuse.AbuseConfig(
        post_requests_per_minute=1,
        read_requests_per_minute=1,
        write_quota_per_day_per_ip=10,
    )
    limited_guard = abuse.InMemoryAbuseGuard(config=limited_cfg)
    assert limited_guard.allow_snapshot_create("198.51.100.9") == (True, "")
    assert limited_guard.allow_snapshot_create("198.51.100.9") == (
        False,
        "Rate limit exceeded for snapshot creation.",
    )

    assert limited_guard.allow_snapshot_read("198.51.100.2") == (True, "")
    assert limited_guard.allow_snapshot_read("198.51.100.2") == (
        False,
        "Rate limit exceeded for snapshot retrieval.",
    )



def test_shared_formatting_and_http_cache_edges() -> None:
    naive = datetime(2026, 2, 17, 12, 0)
    assert formatting.to_utc(naive).tzinfo == timezone.utc
    assert formatting.format_snapshot_taken_at(naive) == "2026-02-17 12:00:00 UTC"

    reference = datetime(2026, 2, 17, 12, 0, tzinfo=timezone.utc)
    future = datetime(2026, 2, 17, 13, 0, tzinfo=timezone.utc)
    assert formatting.format_relative_time(future, reference) == "just now"

    assert formatting.format_compact_views(437) == "437 views"
    assert formatting.format_compact_views(35_000) == "35K views"
    assert formatting.format_compact_views(1_500_000) == "1.5M views"
    assert formatting.format_compact_views(2_400_000_000) == "2.4B views"

    etag = build_etag("api", "Ab12Cd34")
    assert etag == '"api-Ab12Cd34"'
    headers = build_cache_headers(datetime(2026, 2, 20, tzinfo=timezone.utc), etag)
    assert headers["ETag"] == etag
    assert if_none_match_matches(None, etag) is False
    assert if_none_match_matches("*", etag) is True
    assert if_none_match_matches('"other", "api-Ab12Cd34"', etag) is True



def test_shared_models_validation_and_serialization() -> None:
    payload = RecommendationPayload.parse_obj(
        {"videos": ["lzChIIJMpGk"], "shorts": ["dQw4w9WgXcQ"]}
    )
    assert payload.videos[0].video_hash == "lzChIIJMpGk"
    assert payload.shorts[0].video_hash == "dQw4w9WgXcQ"

    with pytest.raises(PydanticValidationError):
        RecommendationPayload.parse_obj({"videos": [{"videoHash": "invalid", "title": "bad"}], "shorts": []})

    with pytest.raises(PydanticValidationError):
        RecommendationPayload.parse_obj(
            {
                "videos": [
                    {"videoHash": "lzChIIJMpGk", "title": "A"},
                    {"videoHash": "lzChIIJMpGk", "title": "B"},
                ],
                "shorts": [],
            }
        )

    with pytest.raises(PydanticValidationError):
        CreateSnapshotResponse.parse_obj({"hash": "bad", "expiresAt": "2026-02-24T00:00:00Z"})

    with pytest.raises(PydanticValidationError):
        RecommendationPayload.parse_obj({"videos": "not-a-list", "shorts": []})

    too_many = [{"videoHash": f"v{index:010d}", "title": str(index)} for index in range(201)]
    with pytest.raises(PydanticValidationError):
        RecommendationPayload.parse_obj({"videos": too_many, "shorts": []})

    defaults = RecommendationPayload.parse_obj({})
    assert defaults.videos == []

    parsed = parse_create_snapshot_request_json('{"videos":["lzChIIJMpGk"],"shorts":[]}')
    dumped = model_to_json_dict(parsed, by_alias=True, exclude_none=True)
    dumped_videos = cast(list[dict[str, object]], dumped["videos"])
    assert dumped_videos[0]["videoHash"] == "lzChIIJMpGk"



def test_shared_rendering_helper_branches() -> None:
    now = datetime(2026, 2, 17, 12, 0, tzinfo=timezone.utc)

    assert rendering._render_video_grid([], now) == '<p class="empty">No videos.</p>'
    assert rendering._render_shorts_grid([], now) == '<p class="empty">No shorts.</p>'

    item = RecommendationItem.parse_obj({"videoHash": "lzChIIJMpGk", "title": "No channel", "viewCount": 1000})
    assert rendering._render_short_card_metadata(item, now) == '<div class="meta-line">1K views</div>'

    with_channel = RecommendationItem.parse_obj(
        {
            "videoHash": "dQw4w9WgXcQ",
            "title": "Channel",
            "channelLink": "https://www.youtube.com/@name",
        }
    )
    channel_html = rendering._render_channel_name(with_channel, include_fallback=True)
    assert 'href="https://www.youtube.com/@name"' in channel_html
    assert "@name" in channel_html
    short_with_channel = rendering._render_short_card_metadata(with_channel, now)
    assert 'class="channel-line"' in short_with_channel

    unknown = RecommendationItem.parse_obj({"videoHash": "YooEa0JVM_A", "title": "Unknown"})
    assert rendering._render_channel_name(unknown, include_fallback=False) == ""
    assert rendering._render_channel_name(unknown, include_fallback=True) == "Unknown channel"
    assert rendering._render_channel_avatar(unknown, include_fallback=False) == ""
    assert "channel-avatar-placeholder" in rendering._render_channel_avatar(unknown, include_fallback=True)

    with_avatar = RecommendationItem.parse_obj(
        {
            "videoHash": "1rInJtz8QWg",
            "title": "Avatar",
            "channelName": "Creator",
            "channelAvatar": "https://yt3.ggpht.com/avatar",
            "publishedAt": "2026-02-17T11:00:00Z",
        }
    )
    avatar_html = rendering._render_channel_avatar(with_avatar, include_fallback=True)
    assert 'src="https://yt3.ggpht.com/avatar"' in avatar_html
    assert 'alt="Creator avatar"' in avatar_html

    assert rendering._channel_name_from_link(None) is None
    assert rendering._channel_name_from_link("") is None
    assert rendering._channel_name_from_link("https://www.youtube.com/@name/") == "@name"

    stats_text = rendering._render_stats_text(with_avatar, now)
    assert stats_text == "1 hour ago"
    assert rendering._render_stats_line(unknown, now) == ""

    snapshot = StoredSnapshot(
        hash="Abcd1234",
        created_at=datetime(2026, 2, 17, 10, 0, tzinfo=timezone.utc),
        expires_at=datetime(2026, 2, 24, 10, 0, tzinfo=timezone.utc),
        payload=_sample_payload(),
    )
    rendered = rendering.render_snapshot_html(snapshot)
    assert "myfyp (my for you page) by" in rendered
    assert "Taken at: <code>2026-02-17 11:00:00 UTC</code>" in rendered
    assert 'href="/privacy"' in rendered

    privacy_rendered = rendering.render_privacy_html()
    assert "Privacy Notice" in privacy_rendered
    assert 'href="/privacy"' in privacy_rendered

    home_rendered = rendering.render_home_html("https://myfyp.link/myfyp.user.js")
    assert "Install and Use" in home_rendered
    assert 'href="/privacy"' in home_rendered
