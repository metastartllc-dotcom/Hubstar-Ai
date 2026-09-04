"""HTTP API entry point for Hubstar AI."""

from fastapi import FastAPI

from app.api.routes.projects import router as projects_router
from app.api.routes.work_items import router as work_items_router
from app.api.routes.materials import router as materials_router
from app.api.routes.work_material_links import router as work_material_links_router
from app.api.routes.work_budget_summaries import router as work_budget_summaries_router
from app.api.routes.project_budget_summaries import router as project_budget_summaries_router


app = FastAPI(title="Hubstar AI", docs_url="/docs")
app.include_router(projects_router)
app.include_router(work_items_router)
app.include_router(materials_router)
app.include_router(work_material_links_router)
app.include_router(work_budget_summaries_router)
app.include_router(project_budget_summaries_router)


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
