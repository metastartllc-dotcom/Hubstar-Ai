"""Database access for materials linked to project work items."""

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.models import Material, Project, WorkItem, WorkMaterialLink
from app.schemas.schemas import WorkMaterialCreateRequest, WorkMaterialUpdateRequest
from app.services.material_calculator import (
    MaterialCalculationError,
    calculate_material_requirement,
)


class LinkedProjectNotFoundError(Exception):
    """Raised when the external project identifier is unknown."""


class LinkedWorkNotFoundError(Exception):
    """Raised when work is unknown or does not belong to the URL project."""


class LinkedMaterialNotFoundError(Exception):
    """Raised when the external material identifier is unknown."""


class MissingWorkQuantityError(Exception):
    """Raised when a work item has no quantity for the calculation."""


class WorkMaterialLinkNotFoundError(Exception):
    """Raised when the material is not linked to the requested work."""


class DuplicateWorkMaterialLinkError(Exception):
    """Raised when the material is already linked to the work item."""


class WorkMaterialLinkPersistenceError(Exception):
    """Raised when a work-material database operation fails."""


def _resolve_project_and_work(
    db: Session,
    project_id: str,
    work_id: str,
) -> tuple[Project, WorkItem]:
    project = db.query(Project).filter(Project.project_id == project_id).first()
    if project is None:
        raise LinkedProjectNotFoundError
    work = db.query(WorkItem).filter(WorkItem.work_id == work_id).first()
    if work is None or work.project_id != project.id:
        raise LinkedWorkNotFoundError
    return project, work


def _resolve_material(db: Session, material_id: str) -> Material:
    material = db.query(Material).filter(Material.material_id == material_id).first()
    if material is None:
        raise LinkedMaterialNotFoundError
    return material


def _public_link(
    work: WorkItem,
    material: Material,
    link: WorkMaterialLink,
) -> dict:
    calculation = calculate_material_requirement(
        work_quantity=work.quantity,
        consumption_rate=link.consumption_rate,
        waste_percentage=link.waste_percentage,
        approved_quantity=link.approved_quantity,
        unit_price=material.unit_price,
    )
    return {
        "material_id": material.material_id,
        "name": material.name,
        "specification": material.specification,
        "normalized_unit": material.normalized_unit,
        "unit_price": material.unit_price,
        "consumption_rate": link.consumption_rate,
        "waste_percentage": link.waste_percentage,
        "calculated_quantity": (float(calculation.calculated_quantity)
                                if calculation.calculated_quantity is not None else None),
        "approved_quantity": link.approved_quantity,
        "effective_quantity": (float(calculation.effective_quantity)
                               if calculation.effective_quantity is not None else None),
        "material_total": (
            float(calculation.material_total)
            if calculation.material_total is not None
            else None
        ),
        "status": link.status,
    }


def list_materials_for_work(
    db: Session,
    project_id: str,
    work_id: str,
) -> list[dict]:
    """Return linked materials ordered by the internal link ID."""
    try:
        _, work = _resolve_project_and_work(db, project_id, work_id)
        rows = (
            db.query(WorkMaterialLink, Material)
            .join(Material, Material.id == WorkMaterialLink.material_id)
            .filter(WorkMaterialLink.work_id == work.id)
            .order_by(WorkMaterialLink.id)
            .all()
        )
        return [_public_link(work, material, link) for link, material in rows]
    except (
        LinkedProjectNotFoundError,
        LinkedWorkNotFoundError,
        MissingWorkQuantityError,
        MaterialCalculationError,
    ):
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise WorkMaterialLinkPersistenceError from exc


def update_work_material_link(
    db: Session,
    project_id: str,
    work_id: str,
    material_id: str,
    update: WorkMaterialUpdateRequest,
) -> dict:
    """Resolve ownership and validate the merged calculation before mutation."""
    try:
        _, work = _resolve_project_and_work(db, project_id, work_id)
        material = _resolve_material(db, material_id)
        link = db.query(WorkMaterialLink).filter(
            WorkMaterialLink.work_id == work.id,
            WorkMaterialLink.material_id == material.id,
        ).first()
        if link is None:
            raise WorkMaterialLinkNotFoundError
        if work.quantity is None:
            raise MissingWorkQuantityError
        values = update.model_dump(exclude_unset=True)
        calculation = calculate_material_requirement(
            work_quantity=work.quantity,
            consumption_rate=values.get("consumption_rate", link.consumption_rate),
            waste_percentage=values.get("waste_percentage", link.waste_percentage),
            approved_quantity=values.get("approved_quantity", link.approved_quantity),
            unit_price=material.unit_price,
        )
        for field, value in values.items():
            setattr(link, field, value)
        link.calculated_quantity = float(calculation.calculated_quantity)
        db.commit()
        db.refresh(link)
        return _public_link(work, material, link)
    except SQLAlchemyError as exc:
        db.rollback()
        raise WorkMaterialLinkPersistenceError from exc
    except (LinkedProjectNotFoundError, LinkedWorkNotFoundError,
            LinkedMaterialNotFoundError, WorkMaterialLinkNotFoundError,
            MissingWorkQuantityError, MaterialCalculationError):
        db.rollback()
        raise


def create_work_material_link(
    db: Session,
    project_id: str,
    work_id: str,
    link_data: WorkMaterialCreateRequest,
) -> dict:
    """Resolve external IDs, calculate quantities, and persist one link."""
    try:
        _, work = _resolve_project_and_work(db, project_id, work_id)
        material = _resolve_material(db, link_data.material_id)
        if work.quantity is None:
            raise MissingWorkQuantityError

        duplicate = (
            db.query(WorkMaterialLink)
            .filter(
                WorkMaterialLink.work_id == work.id,
                WorkMaterialLink.material_id == material.id,
            )
            .first()
        )
        if duplicate is not None:
            raise DuplicateWorkMaterialLinkError

        calculation = calculate_material_requirement(
            work_quantity=work.quantity,
            consumption_rate=link_data.consumption_rate,
            waste_percentage=link_data.waste_percentage,
            approved_quantity=link_data.approved_quantity,
            unit_price=material.unit_price,
        )
        link = WorkMaterialLink(
            work_id=work.id,
            material_id=material.id,
            consumption_rate=link_data.consumption_rate,
            waste_percentage=link_data.waste_percentage,
            calculated_quantity=float(calculation.calculated_quantity),
            approved_quantity=link_data.approved_quantity,
            status=link_data.status,
        )
        db.add(link)
        db.commit()
        db.refresh(link)
        return _public_link(work, material, link)
    except DuplicateWorkMaterialLinkError:
        db.rollback()
        raise
    except (
        LinkedProjectNotFoundError,
        LinkedWorkNotFoundError,
        LinkedMaterialNotFoundError,
        MissingWorkQuantityError,
        MaterialCalculationError,
    ):
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise WorkMaterialLinkPersistenceError from exc
