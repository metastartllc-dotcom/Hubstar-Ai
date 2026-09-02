"""Nested project work-item API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.work_items import (
    DuplicateWorkIdError,
    WorkItemPersistenceError,
    create_work_item,
    list_work_items_for_project,
)
from app.schemas.schemas import ProjectWorkItemCreate, ProjectWorkItemResponse


router = APIRouter(
    prefix="/api/v1/projects/{project_id}/work-items",
    tags=["work-items"],
)


@router.get("", response_model=list[ProjectWorkItemResponse])
def read_project_work_items(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> list[ProjectWorkItemResponse]:
    """Return a paginated list for an external project ID."""
    try:
        work_items = list_work_items_for_project(db, project_id, offset, limit)
    except WorkItemPersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to read work items",
        ) from exc
    if work_items is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return work_items


@router.post(
    "",
    response_model=ProjectWorkItemResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_project_work_item(
    project_id: str,
    work_item_data: ProjectWorkItemCreate,
    db: Annotated[Session, Depends(get_db)],
) -> ProjectWorkItemResponse:
    """Create a work item beneath an external project ID."""
    try:
        work_item = create_work_item(db, project_id, work_item_data)
    except DuplicateWorkIdError as exc:
        raise HTTPException(status_code=409, detail="Work ID already exists") from exc
    except WorkItemPersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create work item",
        ) from exc
    if work_item is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return work_item
