from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
import html

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.responses import Response

from for_us_api.abuse import AbuseConfig, InMemoryAbuseGuard
from for_us_api.models import CreateSnapshotRequest, CreateSnapshotResponse, RecommendationItem, StoredSnapshot
from for_us_api.store import SnapshotStore


def create_app(
    store: SnapshotStore | None = None,
    abuse_guard: InMemoryAbuseGuard | None = None,
) -> FastAPI:
    """Create and configure the API application."""
    snapshot_store = store or SnapshotStore.from_environment()
    guard = abuse_guard or InMemoryAbuseGuard(AbuseConfig())

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        snapshot_store.initialize()
        yield

    app = FastAPI(title="For Us API", version="0.1.0", lifespan=lifespan)

    @app.middleware("http")
    async def enforce_snapshot_body_size(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:  # pyright: ignore[reportUnusedFunction]
        if request.method == "POST" and request.url.path == "/api/snapshots":
            content_length = request.headers.get("content-length")
            if content_length is not None:
                try:
                    parsed_length = int(content_length)
                except ValueError:
                    return JSONResponse(
                        status_code=400,
                        content={"detail": "Invalid Content-Length header."},
                    )
                if parsed_length > guard.config.max_snapshot_body_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": "Request body too large."},
                    )

            body = await request.body()
            if len(body) > guard.config.max_snapshot_body_bytes:
                return JSONResponse(
                    status_code=413,
                    content={"detail": "Request body too large."},
                )
        return await call_next(request)

    @app.get("/health")
    def health() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        return {"status": "ok"}

    @app.post("/api/snapshots", status_code=201, response_model=CreateSnapshotResponse)
    def create_snapshot(request: Request, payload: CreateSnapshotRequest) -> CreateSnapshotResponse:  # pyright: ignore[reportUnusedFunction]
        allowed, reason = guard.allow_snapshot_create(_client_ip(request))
        if not allowed:
            raise HTTPException(status_code=429, detail=reason)
        return snapshot_store.create_snapshot(payload)

    @app.get(
        "/api/snapshots/{snapshot_hash}",
        response_model=CreateSnapshotRequest,
        response_model_exclude_none=True,
    )
    def get_snapshot(request: Request, snapshot_hash: str) -> CreateSnapshotRequest:  # pyright: ignore[reportUnusedFunction]
        allowed, reason = guard.allow_snapshot_read(_client_ip(request))
        if not allowed:
            raise HTTPException(status_code=429, detail=reason)
        snapshot, is_expired = snapshot_store.get_snapshot(snapshot_hash)
        if is_expired:
            raise HTTPException(status_code=410, detail="Snapshot has expired.")
        if snapshot is None:
            raise HTTPException(status_code=404, detail="Snapshot not found.")
        return snapshot.payload

    @app.get("/{snapshot_hash}", response_class=HTMLResponse)
    def render_snapshot_page(request: Request, snapshot_hash: str) -> HTMLResponse:  # pyright: ignore[reportUnusedFunction]
        allowed, _reason = guard.allow_snapshot_read(_client_ip(request))
        if not allowed:
            return HTMLResponse("<h1>429 Too Many Requests</h1>", status_code=429)
        snapshot, is_expired = snapshot_store.get_snapshot(snapshot_hash)
        if is_expired:
            return HTMLResponse("<h1>410 Snapshot expired</h1>", status_code=410)
        if snapshot is None:
            return HTMLResponse("<h1>404 Snapshot not found</h1>", status_code=404)
        return HTMLResponse(_render_snapshot_html(snapshot), status_code=200)

    return app


app = create_app()


def _render_snapshot_html(snapshot: StoredSnapshot) -> str:
    videos = _render_video_grid(snapshot.payload.videos)
    shorts = _render_shorts_grid(snapshot.payload.shorts)
    escaped_hash = html.escape(snapshot.hash)
    return f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>For Us Page - {escaped_hash}</title>
    <style>
      :root {{
        --bg: #0f0f0f;
        --card: #181818;
        --text: #f1f1f1;
        --muted: #aaaaaa;
      }}

      * {{
        box-sizing: border-box;
      }}

      body {{
        margin: 0;
        background: var(--bg);
        color: var(--text);
        font-family: Arial, sans-serif;
      }}

      main {{
        max-width: 2400px;
        margin: 0 auto;
        padding: 20px;
      }}

      h1 {{
        margin: 0 0 8px;
        font-size: 28px;
      }}

      .meta {{
        margin: 0 0 24px;
        color: var(--muted);
      }}

      .section-title {{
        margin: 24px 0 12px;
        font-size: 22px;
      }}

      .videos-grid {{
        display: grid;
        grid-template-columns: repeat(6, 365px);
        gap: 16px;
        justify-content: center;
      }}

      .shorts-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fill, 365px);
        gap: 16px;
        justify-content: center;
      }}

      .video-card {{
        width: 365px;
        height: 305px;
        background: var(--card);
        border-radius: 10px;
        overflow: hidden;
      }}

      .short-card {{
        width: 365px;
        height: 547px;
        background: var(--card);
        border-radius: 10px;
        overflow: hidden;
      }}

      .thumb {{
        display: block;
      }}

      .video-card .thumb img {{
        width: 365px;
        height: 205px;
        object-fit: cover;
        display: block;
      }}

      .short-card .thumb img {{
        width: 365px;
        height: 487px;
        object-fit: cover;
        display: block;
      }}

      .title {{
        margin: 0;
        font-size: 14px;
        line-height: 1.25;
        color: var(--text);
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
      }}

      .empty {{
        color: var(--muted);
      }}

      .card-body {{
        padding: 10px 12px;
      }}

      .meta-line {{
        margin-top: 6px;
        color: var(--muted);
        font-size: 12px;
        line-height: 1.25;
      }}

      .channel {{
        display: flex;
        align-items: center;
        gap: 8px;
        margin-top: 8px;
      }}

      .channel-avatar {{
        width: 22px;
        height: 22px;
        border-radius: 999px;
        object-fit: cover;
        flex-shrink: 0;
      }}

      .channel-name {{
        color: var(--muted);
        font-size: 12px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }}

      .channel-name a {{
        color: inherit;
        text-decoration: none;
      }}

      .channel-name a:hover {{
        text-decoration: underline;
      }}

      @media (max-width: 2280px) {{
        .videos-grid {{
          grid-template-columns: repeat(4, 365px);
        }}
      }}

      @media (max-width: 1520px) {{
        .videos-grid {{
          grid-template-columns: repeat(3, 365px);
        }}
      }}

      @media (max-width: 1140px) {{
        .videos-grid,
        .shorts-grid {{
          grid-template-columns: repeat(2, 365px);
        }}
      }}

      @media (max-width: 760px) {{
        .videos-grid,
        .shorts-grid {{
          grid-template-columns: repeat(1, 365px);
        }}
      }}
    </style>
  </head>
  <body>
    <main>
      <h1>For Us Page</h1>
      <p class="meta">Snapshot hash: <code>{escaped_hash}</code></p>
      <h2 class="section-title">Videos</h2>
      {videos}
      <h2 class="section-title">Shorts</h2>
      {shorts}
    </main>
  </body>
</html>
"""


def _render_video_grid(items: list[RecommendationItem]) -> str:
    if not items:
        return '<p class="empty">No videos.</p>'

    list_items: list[str] = []
    for item in items:
        escaped_hash = html.escape(item.video_hash)
        escaped_title = html.escape(item.title)
        href = f"https://www.youtube.com/watch?v={escaped_hash}"
        thumb = f"https://i.ytimg.com/vi/{escaped_hash}/hqdefault.jpg"
        list_items.append(
            (
                '<article class="video-card">'
                f'<a class="thumb" href="{href}" target="_blank" rel="noopener noreferrer">'
                f'<img src="{thumb}" alt="{escaped_title} thumbnail" loading="lazy">'
                "</a>"
                '<div class="card-body">'
                f'<h3 class="title">{escaped_title}</h3>'
                f"{_render_card_metadata(item)}"
                "</div>"
                "</article>"
            )
        )
    return f'<section class="videos-grid">{"".join(list_items)}</section>'


def _render_shorts_grid(items: list[RecommendationItem]) -> str:
    if not items:
        return '<p class="empty">No shorts.</p>'

    list_items: list[str] = []
    for item in items:
        escaped_hash = html.escape(item.video_hash)
        escaped_title = html.escape(item.title)
        href = f"https://www.youtube.com/shorts/{escaped_hash}"
        thumb = f"https://i.ytimg.com/vi/{escaped_hash}/hqdefault.jpg"
        list_items.append(
            (
                '<article class="short-card">'
                f'<a class="thumb" href="{href}" target="_blank" rel="noopener noreferrer">'
                f'<img src="{thumb}" alt="{escaped_title} short thumbnail" loading="lazy">'
                "</a>"
                '<div class="card-body">'
                f'<h3 class="title">{escaped_title}</h3>'
                f"{_render_card_metadata(item)}"
                "</div>"
                "</article>"
            )
        )
    return f'<section class="shorts-grid">{"".join(list_items)}</section>'


def _render_card_metadata(item: RecommendationItem) -> str:
    channel_html = _render_channel(item)
    stats_html = _render_stats(item)
    return f"{channel_html}{stats_html}"


def _render_channel(item: RecommendationItem) -> str:
    if item.channel_name is None:
        return ""

    name = html.escape(item.channel_name)
    name_html = name
    if item.channel_link is not None:
        escaped_link = html.escape(str(item.channel_link))
        name_html = f'<a href="{escaped_link}" target="_blank" rel="noopener noreferrer">{name}</a>'

    avatar_html = ""
    if item.channel_avatar is not None:
        escaped_avatar = html.escape(str(item.channel_avatar))
        avatar_html = f'<img class="channel-avatar" src="{escaped_avatar}" alt="{name} avatar" loading="lazy">'

    return f'<div class="channel">{avatar_html}<div class="channel-name">{name_html}</div></div>'


def _render_stats(item: RecommendationItem) -> str:
    parts: list[str] = []
    if item.view_count is not None:
        parts.append(f"{item.view_count:,} views")
    if item.published_at is not None:
        parts.append(item.published_at.date().isoformat())
    if not parts:
        return ""
    return f'<div class="meta-line">{html.escape(" • ".join(parts))}</div>'


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client is not None:
        return request.client.host
    return "unknown"
