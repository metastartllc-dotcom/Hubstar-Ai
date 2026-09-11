"""Nested project work-item API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.work_items import (
    DuplicateWorkIdError,
    WorkItemPersistenceError,
    InvalidWorkMasterStatusError,
    WorkMasterNotFoundError,
    create_work_item,
    create_work_item_from_master,
    list_work_items_for_project,
    update_work_item,
)
from app.schemas.schemas import ProjectWorkItemCreate, ProjectWorkItemFromMasterCreate, ProjectWorkItemResponse, WorkItemUpdateRequest, WorkItemPatchResponse


router = APIRouter(
    prefix="/api/v1/projects/{project_id}/work-items",
    tags=["work-items"],
)


@router.post(
    "/from-master",
    response_model=WorkItemPatchResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_project_work_item_from_master(
    project_id: str,
    request: ProjectWorkItemFromMasterCreate,
    db: Annotated[Session, Depends(get_db)],
) -> WorkItemPatchResponse:
    try:
        work = create_work_item_from_master(db, project_id, request)
    except WorkMasterNotFoundError as exc:
        raise HTTPException(404, detail="Work master not found") from exc
    except InvalidWorkMasterStatusError as exc:
        raise HTTPException(409, detail="Work master status does not allow project work creation") from exc
    except DuplicateWorkIdError as exc:
        raise HTTPException(409, detail="Work ID already exists") from exc
    except WorkItemPersistenceError as exc:
        raise HTTPException(500, detail="Unable to create work item") from exc
    if work is None:
        raise HTTPException(404, detail="Project not found")
    return work


@router.patch("/{work_id}", response_model=WorkItemPatchResponse)
def patch_project_work_item(
    project_id: str, work_id: str, update: WorkItemUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
) -> WorkItemPatchResponse:
    try:
        work = update_work_item(db, project_id, work_id, update)
    except WorkItemPersistenceError as exc:
        raise HTTPException(500, detail="Unable to update work item") from exc
    if work is None:
        raise HTTPException(404, detail="Project or work item not found")
    return work


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
