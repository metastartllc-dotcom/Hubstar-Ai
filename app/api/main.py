"""HTTP API entry point for Hubstar AI."""

from fastapi import FastAPI

from app.api.routes.projects import router as projects_router


app = FastAPI(title="Hubstar AI", docs_url="/docs")
app.include_router(projects_router)


@app.get("/")
def read_root() -> dict[str, str]:
    """Return basic service metadata."""
    return {
        "name": "Hubstar AI",
        "status": "ok",
        "docs": "/docs",
    }


@app.get("/health")
def read_health() -> dict[str, str]:
    """Return the service health status."""
    return {"status": "ok"}
