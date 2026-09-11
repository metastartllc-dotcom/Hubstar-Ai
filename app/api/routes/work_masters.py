"""Reusable work-master catalog API."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.work_masters import (
    DuplicateWorkMasterIdError,
    DuplicateWorkMasterSourceError,
    WorkMasterPersistenceError,
    create_work_master,
    get_work_master_by_work_master_id,
    list_work_masters,
)
from app.schemas.schemas import WorkMasterCreateRequest, WorkMasterPublicResponse

router = APIRouter(prefix="/api/v1/work-masters", tags=["work-masters"])


@router.get("", response_model=list[WorkMasterPublicResponse])
def read_work_masters(
    db: Annotated[Session, Depends(get_db)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> list[WorkMasterPublicResponse]:
    try:
        return list_work_masters(db, offset, limit)
    except WorkMasterPersistenceError as exc:
        raise HTTPException(500, detail="Unable to read work masters") from exc


@router.get("/{work_master_id}", response_model=WorkMasterPublicResponse)
def read_work_master(
    work_master_id: str, db: Annotated[Session, Depends(get_db)]
) -> WorkMasterPublicResponse:
    try:
        master = get_work_master_by_work_master_id(db, work_master_id)
    except WorkMasterPersistenceError as exc:
        raise HTTPException(500, detail="Unable to read work master") from exc
    if master is None:
        raise HTTPException(404, detail="Work master not found")
    return master


@router.post("", response_model=WorkMasterPublicResponse, status_code=status.HTTP_201_CREATED)
def post_work_master(
    request: WorkMasterCreateRequest, db: Annotated[Session, Depends(get_db)]
) -> WorkMasterPublicResponse:
    try:
        return create_work_master(db, request)
    except DuplicateWorkMasterIdError as exc:
        raise HTTPException(409, detail="Work master ID already exists") from exc
    except DuplicateWorkMasterSourceError as exc:
        raise HTTPException(409, detail="Work master source already exists") from exc
    except WorkMasterPersistenceError as exc:
        raise HTTPException(500, detail="Unable to create work master") from exc
