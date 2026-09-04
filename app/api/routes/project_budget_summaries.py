"""Read-only project budget API."""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.repositories.project_budget_summaries import (
    get_project_budget_summary, ProjectBudgetNotFoundError, ProjectBudgetPersistenceError,
)
from app.schemas.schemas import ProjectBudgetSummaryResponse

router = APIRouter(prefix="/api/v1/projects", tags=["project-budget"])


@router.get("/{project_id}/budget-summary", response_model=ProjectBudgetSummaryResponse)
def read_project_budget(project_id: str, db: Annotated[Session, Depends(get_db)]):
    try:
        return get_project_budget_summary(db, project_id)
    except ProjectBudgetNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except ProjectBudgetPersistenceError as exc:
        raise HTTPException(status_code=500, detail="Unable to read project budget") from exc
