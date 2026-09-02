"""Read-only project API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.projects import (
    get_project_by_project_id,
    list_projects,
)
from app.schemas.schemas import ProjectResponse


router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.get("", response_model=list[ProjectResponse])
def read_projects(
    db: Annotated[Session, Depends(get_db)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> list[ProjectResponse]:
    """Return a paginated list of projects."""
    return list_projects(db, offset=offset, limit=limit)


@router.get("/{project_id}", response_model=ProjectResponse)
def read_project(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> ProjectResponse:
    """Return a project by its external project identifier."""
    project = get_project_by_project_id(db, project_id=project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    return project
