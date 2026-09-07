from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.repositories.work_equipment_links import (DuplicateWorkEquipmentError, WorkEquipmentNotFoundError,
    WorkEquipmentPersistenceError, WorkEquipmentValidationError, InvalidEquipmentConfigurationError, create_work_equipment_link,
    list_work_equipment_links, update_work_equipment_link)
from app.schemas.schemas import WorkEquipmentCreateRequest, WorkEquipmentPublicResponse, WorkEquipmentUpdateRequest

router = APIRouter(prefix="/api/v1/projects/{project_id}/work-items/{work_id}/equipment", tags=["work-equipment"])

def _error(exc):
    if isinstance(exc, WorkEquipmentNotFoundError): return HTTPException(404, "Resource not found")
    if isinstance(exc, DuplicateWorkEquipmentError): return HTTPException(409, "Equipment is already linked to this work item")
    if isinstance(exc, InvalidEquipmentConfigurationError): return HTTPException(409, "Equipment is not eligible for linking")
    if isinstance(exc, WorkEquipmentValidationError): return HTTPException(422, "Equipment snapshot fields are inconsistent")
    return HTTPException(500, "Unable to persist work equipment")

@router.get("", response_model=list[WorkEquipmentPublicResponse])
def get_links(project_id: str, work_id: str, db: Annotated[Session, Depends(get_db)]):
    try: return list_work_equipment_links(db, project_id, work_id)
    except (WorkEquipmentNotFoundError, WorkEquipmentPersistenceError) as exc: raise _error(exc) from exc

@router.post("", response_model=WorkEquipmentPublicResponse, status_code=201)
def post_link(project_id: str, work_id: str, request: WorkEquipmentCreateRequest, db: Annotated[Session, Depends(get_db)]):
    try: return create_work_equipment_link(db, project_id, work_id, request)
    except (WorkEquipmentNotFoundError, DuplicateWorkEquipmentError, WorkEquipmentValidationError,
            InvalidEquipmentConfigurationError, WorkEquipmentPersistenceError) as exc: raise _error(exc) from exc

@router.patch("/{equipment_id}", response_model=WorkEquipmentPublicResponse)
def patch_link(project_id: str, work_id: str, equipment_id: str, request: WorkEquipmentUpdateRequest,
               db: Annotated[Session, Depends(get_db)]):
    try: return update_work_equipment_link(db, project_id, work_id, equipment_id, request)
    except (WorkEquipmentNotFoundError, WorkEquipmentValidationError, WorkEquipmentPersistenceError) as exc: raise _error(exc) from exc
