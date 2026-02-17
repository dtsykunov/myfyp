from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from for_us_worker.app import handle_fetch, handle_scheduled

try:
    from workers import Response, WorkerEntrypoint
except ModuleNotFoundError:  # pragma: no cover - local test fallback
    class WorkerEntrypoint:  # type: ignore[override]
        env: Any

    class Response:  # type: ignore[override]
        def __init__(
            self,
            body: str,
            *,
            status: int = 200,
            headers: Mapping[str, str] | None = None,
        ) -> None:
            self.body = body
            self.status = status
            self.headers = dict(headers or {})


class Default(WorkerEntrypoint):
    async def fetch(self, request: Any) -> Response:
        response_spec = await handle_fetch(request=request, env=self.env)
        return Response(response_spec.body, status=response_spec.status, headers=response_spec.headers)

    async def scheduled(self, controller: Any, env: Any, ctx: Any) -> None:
        del controller, ctx
        await handle_scheduled(env)
