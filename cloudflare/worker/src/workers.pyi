from typing import Any, Mapping


class Response:
    def __init__(self, body: str, *, status: int = 200, headers: Mapping[str, str] | None = ...) -> None: ...


class WorkerEntrypoint:
    env: Any
