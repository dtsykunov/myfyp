from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from for_us_api.models import CreateSnapshotRequest, CreateSnapshotResponse
from for_us_api.store import SnapshotStore


def create_app(store: SnapshotStore | None = None) -> FastAPI:
    """Create and configure the API application."""
    snapshot_store = store or SnapshotStore.from_environment()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        snapshot_store.initialize()
        yield

    app = FastAPI(title="For Us API", version="0.1.0", lifespan=lifespan)

    @app.get("/health")
    def health() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        return {"status": "ok"}

    @app.post("/api/snapshots", status_code=201, response_model=CreateSnapshotResponse)
    def create_snapshot(payload: CreateSnapshotRequest) -> CreateSnapshotResponse:  # pyright: ignore[reportUnusedFunction]
        return snapshot_store.create_snapshot(payload)

    return app


app = create_app()
