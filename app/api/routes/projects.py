"""Read-only project API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.projects import (
    DuplicateProjectIdError,
    InvalidProjectDateRangeError,
    ProjectCreationError,
    ProjectUpdateError,
    create_project,
    get_project_by_project_id,
    list_projects,
    update_project,
)
from app.schemas.schemas import ProjectCreate, ProjectResponse, ProjectUpdate


router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_new_project(
    project_data: ProjectCreate,
    db: Annotated[Session, Depends(get_db)],
) -> ProjectResponse:
    """Create a project for local development use."""
    try:
        return create_project(db, project_data)
    except DuplicateProjectIdError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project ID already exists",
        ) from exc
    except ProjectCreationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create project",
        ) from exc


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


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_existing_project(
    project_id: str,
    project_data: ProjectUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> ProjectResponse:
    """Partially update a project without changing its external ID."""
    try:
        project = update_project(db, project_id, project_data)
    except InvalidProjectDateRangeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="start_date must be on or before end_date",
        ) from exc
    except ProjectUpdateError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to update project",
        ) from exc

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    return project
