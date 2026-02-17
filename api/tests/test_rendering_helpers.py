# pyright: reportPrivateUsage=false

from __future__ import annotations

from datetime import datetime, timezone

from for_us_api import rendering
from for_us_api.models import RecommendationItem


def test_render_video_grid_and_shorts_grid_empty() -> None:
    now = datetime(2026, 2, 17, 12, 0, tzinfo=timezone.utc)
    assert rendering._render_video_grid([], now) == '<p class="empty">No videos.</p>'
    assert rendering._render_shorts_grid([], now) == '<p class="empty">No shorts.</p>'


def test_render_short_metadata_handles_missing_and_present_channel() -> None:
    now = datetime(2026, 2, 17, 12, 0, tzinfo=timezone.utc)
    without_channel = RecommendationItem.model_validate(
        {"videoHash": "lzChIIJMpGk", "title": "No channel", "viewCount": 1_000}
    )
    metadata_without_channel = rendering._render_short_card_metadata(without_channel, now)
    assert metadata_without_channel == '<div class="meta-line">1K views</div>'

    with_channel = RecommendationItem.model_validate(
        {
            "videoHash": "dQw4w9WgXcQ",
            "title": "Channel present",
            "channelName": "Example",
            "channelLink": "https://www.youtube.com/@example",
        }
    )
    metadata_with_channel = rendering._render_short_card_metadata(with_channel, now)
    assert 'class="channel-line"' in metadata_with_channel
    assert 'href="https://www.youtube.com/@example"' in metadata_with_channel


def test_render_channel_name_and_avatar_variants() -> None:
    unknown = RecommendationItem.model_validate({"videoHash": "lzChIIJMpGk", "title": "Unknown"})
    assert rendering._render_channel_name(unknown, include_fallback=False) == ""
    assert rendering._render_channel_name(unknown, include_fallback=True) == "Unknown channel"
    assert "channel-avatar-placeholder" in rendering._render_channel_avatar(unknown, include_fallback=True)
    assert rendering._render_channel_avatar(unknown, include_fallback=False) == ""

    with_link_only = RecommendationItem.model_validate(
        {
            "videoHash": "dQw4w9WgXcQ",
            "title": "Link only",
            "channelLink": "https://www.youtube.com/@captain",
        }
    )
    channel_html = rendering._render_channel_name(with_link_only, include_fallback=True)
    assert 'href="https://www.youtube.com/@captain"' in channel_html
    assert "@captain" in channel_html

    with_avatar = RecommendationItem.model_validate(
        {
            "videoHash": "YooEa0JVM_A",
            "title": "Avatar",
            "channelName": "Crew",
            "channelAvatar": "https://yt3.ggpht.com/avatar",
        }
    )
    avatar_html = rendering._render_channel_avatar(with_avatar, include_fallback=True)
    assert 'src="https://yt3.ggpht.com/avatar"' in avatar_html
    assert 'alt="Crew avatar"' in avatar_html


def test_channel_name_from_link_edge_cases() -> None:
    assert rendering._channel_name_from_link(None) is None
    assert rendering._channel_name_from_link("") is None
    assert rendering._channel_name_from_link("https://www.youtube.com/@name/") == "@name"


def test_render_stats_helpers_and_relative_time() -> None:
    reference = datetime(2026, 2, 17, 12, 0, tzinfo=timezone.utc)
    with_stats = RecommendationItem.model_validate(
        {
            "videoHash": "lzChIIJMpGk",
            "title": "Stats",
            "viewCount": 1_500_000,
            "publishedAt": "2026-02-17T11:00:00Z",
        }
    )
    stats_text = rendering._render_stats_text(with_stats, reference)
    assert stats_text == "1.5M views • 1 hour ago"
    stats_line = rendering._render_stats_line(with_stats, reference)
    assert stats_line == '<div class="meta-line">1.5M views • 1 hour ago</div>'

    without_stats = RecommendationItem.model_validate(
        {"videoHash": "dQw4w9WgXcQ", "title": "No stats"}
    )
    assert rendering._render_stats_text(without_stats, reference) == ""
    assert rendering._render_stats_line(without_stats, reference) == ""
