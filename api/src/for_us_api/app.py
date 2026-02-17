from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
import html

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.responses import Response

from for_us_api.abuse import AbuseConfig, InMemoryAbuseGuard
from for_us_api.models import CreateSnapshotRequest, CreateSnapshotResponse, StoredSnapshot
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

    @app.get("/api/snapshots/{snapshot_hash}", response_model=CreateSnapshotRequest)
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
    videos = _render_video_list(snapshot.payload.videos, is_short=False)
    shorts = _render_video_list(snapshot.payload.shorts, is_short=True)
    escaped_hash = html.escape(snapshot.hash)
    return f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>For Us Page</title>
  </head>
  <body>
    <main>
      <h1>For Us Page</h1>
      <p>Snapshot hash: <code>{escaped_hash}</code></p>
      <h2>Videos</h2>
      {videos}
      <h2>Shorts</h2>
      {shorts}
    </main>
  </body>
</html>
"""


def _render_video_list(video_hashes: list[str], is_short: bool) -> str:
    if not video_hashes:
        return "<p>No items.</p>"

    list_items: list[str] = []
    for video_hash in video_hashes:
        escaped_hash = html.escape(video_hash)
        if is_short:
            href = f"https://www.youtube.com/shorts/{escaped_hash}"
        else:
            href = f"https://www.youtube.com/watch?v={escaped_hash}"
        list_items.append(
            f'<li><a href="{href}" target="_blank" rel="noopener noreferrer">{escaped_hash}</a></li>'
        )
    return f"<ul>{''.join(list_items)}</ul>"


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client is not None:
        return request.client.host
    return "unknown"
