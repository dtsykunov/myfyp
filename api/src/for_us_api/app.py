from fastapi import FastAPI


def create_app() -> FastAPI:
    """Create and configure the API application."""
    app = FastAPI(title="For Us API", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()

