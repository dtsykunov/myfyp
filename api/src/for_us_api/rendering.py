# pyright: reportPrivateUsage=false, reportUnusedFunction=false

from __future__ import annotations

from datetime import datetime
from typing import cast

from for_us_api.models import RecommendationItem, StoredSnapshot
from for_us_shared import rendering as _shared_rendering
from for_us_shared.models import (
    RecommendationItem as _SharedRecommendationItem,
    StoredSnapshot as _SharedStoredSnapshot,
)


def render_home_html(userscript_url: str, site_url: str | None = None) -> str:
    return _shared_rendering.render_home_html(userscript_url, site_url)


def render_privacy_html() -> str:
    return _shared_rendering.render_privacy_html()


def render_snapshot_html(snapshot: StoredSnapshot) -> str:
    return _shared_rendering.render_snapshot_html(cast(_SharedStoredSnapshot, snapshot))


def _render_video_grid(videos: list[RecommendationItem], now: datetime) -> str:
    return _shared_rendering._render_video_grid(cast(list[_SharedRecommendationItem], videos), now)


def _render_shorts_grid(shorts: list[RecommendationItem], now: datetime) -> str:
    return _shared_rendering._render_shorts_grid(cast(list[_SharedRecommendationItem], shorts), now)


def _render_short_card_metadata(item: RecommendationItem, now: datetime) -> str:
    return _shared_rendering._render_short_card_metadata(cast(_SharedRecommendationItem, item), now)


def _render_channel_name(item: RecommendationItem, include_fallback: bool) -> str:
    return _shared_rendering._render_channel_name(
        cast(_SharedRecommendationItem, item), include_fallback=include_fallback
    )


def _render_channel_avatar(item: RecommendationItem, include_fallback: bool) -> str:
    return _shared_rendering._render_channel_avatar(
        cast(_SharedRecommendationItem, item), include_fallback=include_fallback
    )


def _channel_name_from_link(channel_link: str | None) -> str | None:
    return _shared_rendering._channel_name_from_link(channel_link)


def _render_stats_text(item: RecommendationItem, now: datetime) -> str:
    return _shared_rendering._render_stats_text(cast(_SharedRecommendationItem, item), now)


def _render_stats_line(item: RecommendationItem, now: datetime) -> str:
    return _shared_rendering._render_stats_line(cast(_SharedRecommendationItem, item), now)
