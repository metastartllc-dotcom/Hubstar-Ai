"""Global material master API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.materials import (
    DuplicateMaterialIdError,
    MaterialPersistenceError,
    create_material,
    get_material_by_material_id,
    list_materials,
    update_material,
)
from app.schemas.schemas import (
    MaterialCreateRequest,
    MaterialPublicResponse,
    MaterialUpdateRequest,
)


router = APIRouter(prefix="/api/v1/materials", tags=["materials"])


@router.get("", response_model=list[MaterialPublicResponse])
def read_materials(
    db: Annotated[Session, Depends(get_db)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> list[MaterialPublicResponse]:
    """Return paginated global material master data."""
    try:
        return list_materials(db, offset, limit)
    except MaterialPersistenceError as exc:
        raise HTTPException(status_code=500, detail="Unable to read materials") from exc


@router.get("/{material_id}", response_model=MaterialPublicResponse)
def read_material(
    material_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> MaterialPublicResponse:
    """Return material master data by external identifier."""
    try:
        material = get_material_by_material_id(db, material_id)
    except MaterialPersistenceError as exc:
        raise HTTPException(status_code=500, detail="Unable to read material") from exc
    if material is None:
        raise HTTPException(status_code=404, detail="Material not found")
    return material


@router.post(
    "",
    response_model=MaterialPublicResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_new_material(
    material_data: MaterialCreateRequest,
    db: Annotated[Session, Depends(get_db)],
) -> MaterialPublicResponse:
    """Create material master data for local development use."""
    try:
        return create_material(db, material_data)
    except DuplicateMaterialIdError as exc:
        raise HTTPException(status_code=409, detail="Material ID already exists") from exc
    except MaterialPersistenceError as exc:
        raise HTTPException(status_code=500, detail="Unable to create material") from exc


@router.patch("/{material_id}", response_model=MaterialPublicResponse)
def update_existing_material(
    material_id: str,
    material_data: MaterialUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
) -> MaterialPublicResponse:
    """Partially update mutable material master data."""
    try:
        material = update_material(db, material_id, material_data)
    except MaterialPersistenceError as exc:
        raise HTTPException(status_code=500, detail="Unable to update material") from exc
    if material is None:
        raise HTTPException(status_code=404, detail="Material not found")
    return material
