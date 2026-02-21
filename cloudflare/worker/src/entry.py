# pyright: reportMissingModuleSource=false, reportAssignmentType=false

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from for_us_worker.app import handle_fetch, handle_scheduled

try:
    from workers import Response as WorkersResponse
    from workers import WorkerEntrypoint as WorkersEntrypoint
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


class Default(WorkersEntrypoint):
    async def fetch(self, request: Any) -> WorkersResponse:
        response_spec = await handle_fetch(request=request, env=self.env)
        return WorkersResponse(response_spec.body, status=response_spec.status, headers=response_spec.headers)

    async def scheduled(self, controller: Any, env: Any, ctx: Any) -> None:
        del controller, ctx
        resolved_env = env if env is not None else self.env
        await handle_scheduled(resolved_env)
