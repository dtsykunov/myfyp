# pyright: reportMissingModuleSource=false, reportAssignmentType=false

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from for_us_worker.app import app, handle_fetch, handle_scheduled

try:
    from workers import Response as WorkersResponse
    from workers import WorkerEntrypoint as WorkersEntrypoint
    from workers import asgi as workers_asgi
except ModuleNotFoundError:  # pragma: no cover - local test fallback
    class WorkersEntrypoint:
        env: Any

    class WorkersResponse:
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

    workers_asgi = None


class Default(WorkersEntrypoint):
    async def fetch(self, request: Any) -> WorkersResponse:
        if workers_asgi is not None:
            app.state.env = self.env
            response = await workers_asgi.fetch(app, request, self.env)
            return cast(WorkersResponse, response)

        response_spec = await handle_fetch(request=request, env=self.env)
        return WorkersResponse(response_spec.body, status=response_spec.status, headers=response_spec.headers)

    async def scheduled(self, controller: Any, env: Any, ctx: Any) -> None:
        del controller, ctx
        await handle_scheduled(env)
