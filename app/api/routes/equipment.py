"""Equipment master API; no work links or total-cost calculations."""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.repositories.equipment import (
    DuplicateEquipmentIdError, EquipmentPersistenceError,
    create_equipment, get_equipment_by_equipment_id, list_equipment,
)
from app.schemas.schemas import EquipmentCreateRequest, EquipmentPublicResponse

router = APIRouter(prefix="/api/v1/equipment", tags=["equipment"])


@router.get("", response_model=list[EquipmentPublicResponse])
def read_equipment_list(
    db: Annotated[Session, Depends(get_db)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
):
    try:
        return list_equipment(db, offset, limit)
    except EquipmentPersistenceError as exc:
        raise HTTPException(500, "Unable to read equipment") from exc


@router.get("/{equipment_id}", response_model=EquipmentPublicResponse)
def read_equipment(equipment_id: str, db: Annotated[Session, Depends(get_db)]):
    try:
        equipment = get_equipment_by_equipment_id(db, equipment_id)
    except EquipmentPersistenceError as exc:
        raise HTTPException(500, "Unable to read equipment") from exc
    if equipment is None:
        raise HTTPException(404, "Equipment not found")
    return equipment


@router.post("", response_model=EquipmentPublicResponse, status_code=201)
def post_equipment(request: EquipmentCreateRequest, db: Annotated[Session, Depends(get_db)]):
    try:
        return create_equipment(db, request)
    except DuplicateEquipmentIdError as exc:
        raise HTTPException(409, "Equipment ID already exists") from exc
    except EquipmentPersistenceError as exc:
        raise HTTPException(500, "Unable to create equipment") from exc
