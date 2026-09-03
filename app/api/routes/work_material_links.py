"""Nested work-item material API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.work_material_links import (
    DuplicateWorkMaterialLinkError,
    LinkedMaterialNotFoundError,
    LinkedProjectNotFoundError,
    LinkedWorkNotFoundError,
    MissingWorkQuantityError,
    WorkMaterialLinkPersistenceError,
    create_work_material_link,
    list_materials_for_work,
)
from app.schemas.schemas import WorkMaterialCreateRequest, WorkMaterialPublicResponse
from app.services.material_calculator import MaterialCalculationError


router = APIRouter(
    prefix="/api/v1/projects/{project_id}/work-items/{work_id}/materials",
    tags=["work-materials"],
)


def _raise_not_found(exc: Exception) -> None:
    if isinstance(exc, LinkedProjectNotFoundError):
        detail = "Project not found"
    elif isinstance(exc, LinkedWorkNotFoundError):
        detail = "Work item not found"
    else:
        detail = "Material not found"
    raise HTTPException(status_code=404, detail=detail) from exc


@router.get("", response_model=list[WorkMaterialPublicResponse])
def read_work_materials(
    project_id: str,
    work_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> list[WorkMaterialPublicResponse]:
    """Return materials linked to one project-owned work item."""
    try:
        return list_materials_for_work(db, project_id, work_id)
    except (LinkedProjectNotFoundError, LinkedWorkNotFoundError) as exc:
        _raise_not_found(exc)
    except (MissingWorkQuantityError, MaterialCalculationError) as exc:
        raise HTTPException(status_code=422, detail="Invalid material calculation") from exc
    except WorkMaterialLinkPersistenceError as exc:
        raise HTTPException(status_code=500, detail="Unable to read work materials") from exc


@router.post(
    "",
    response_model=WorkMaterialPublicResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_work_material(
    project_id: str,
    work_id: str,
    link_data: WorkMaterialCreateRequest,
    db: Annotated[Session, Depends(get_db)],
) -> WorkMaterialPublicResponse:
    """Link material master data to a project-owned work item."""
    try:
        return create_work_material_link(db, project_id, work_id, link_data)
    except (
        LinkedProjectNotFoundError,
        LinkedWorkNotFoundError,
        LinkedMaterialNotFoundError,
    ) as exc:
        _raise_not_found(exc)
    except DuplicateWorkMaterialLinkError as exc:
        raise HTTPException(status_code=409, detail="Material already linked") from exc
    except (MissingWorkQuantityError, MaterialCalculationError) as exc:
        raise HTTPException(status_code=422, detail="Invalid material calculation") from exc
    except WorkMaterialLinkPersistenceError as exc:
        raise HTTPException(status_code=500, detail="Unable to link material") from exc
