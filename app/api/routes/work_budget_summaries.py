"""Read-only work budget summary endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.work_budget_summaries import (
    SummaryProjectNotFoundError,
    SummaryWorkNotFoundError,
    WorkBudgetSummaryPersistenceError,
    get_work_budget_summary,
)
from app.schemas.schemas import WorkBudgetSummaryResponse


router = APIRouter(
    prefix="/api/v1/projects/{project_id}/work-items/{work_id}/summary",
    tags=["work-budget"],
)


@router.get("", response_model=WorkBudgetSummaryResponse)
def read_work_budget_summary(
    project_id: str,
    work_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> WorkBudgetSummaryResponse:
    """Return known labor and material amounts without database writes."""
    try:
        return get_work_budget_summary(db, project_id, work_id)
    except SummaryProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except SummaryWorkNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Work item not found") from exc
    except WorkBudgetSummaryPersistenceError as exc:
        raise HTTPException(status_code=500, detail="Unable to read work budget") from exc
