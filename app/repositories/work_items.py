"""Database access for project work items."""

from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.models import WorkItem
from app.repositories.projects import get_project_by_project_id
from app.schemas.schemas import ProjectWorkItemCreate, WorkItemUpdateRequest


class DuplicateWorkIdError(Exception):
    """Raised when a global external work identifier already exists."""


class WorkItemPersistenceError(Exception):
    """Raised when a work item database operation fails."""


def update_work_item(db: Session, project_id: str, work_id: str,
                     update: WorkItemUpdateRequest) -> WorkItem | None:
    """Update one owned work item without modifying material links."""
    try:
        project = get_project_by_project_id(db, project_id)
        if project is None:
            return None
        work = get_work_item_by_work_id(db, work_id)
        if work is None or work.project_id != project.id:
            return None
        values = update.model_dump(exclude_unset=True)
        if "quantity" in values or "labor_unit_rate" in values:
            values["labor_total"] = _calculate_labor_total(
                values.get("quantity", work.quantity),
                values.get("labor_unit_rate", work.labor_unit_rate),
            )
        for field, value in values.items():
            setattr(work, field, value)
        db.commit()
        db.refresh(work)
        return work
    except SQLAlchemyError as exc:
        db.rollback()
        raise WorkItemPersistenceError from exc


def get_work_item_by_work_id(db: Session, work_id: str) -> WorkItem | None:
    """Return a work item by its globally unique external identifier."""
    return db.query(WorkItem).filter(WorkItem.work_id == work_id).first()


def list_work_items_for_project(
    db: Session,
    project_id: str,
    offset: int,
    limit: int,
) -> list[WorkItem] | None:
    """List one external project's work items in stable database order."""
    try:
        project = get_project_by_project_id(db, project_id)
        if project is None:
            return None
        return (
            db.query(WorkItem)
            .filter(WorkItem.project_id == project.id)
            .order_by(WorkItem.id)
            .offset(offset)
            .limit(limit)
            .all()
        )
    except SQLAlchemyError as exc:
        raise WorkItemPersistenceError from exc


def _calculate_labor_total(
    quantity: float | None,
    labor_unit_rate: float | None,
) -> float | None:
    if quantity is None or labor_unit_rate is None:
        return None
    total = Decimal(str(quantity)) * Decimal(str(labor_unit_rate))
    return float(total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def create_work_item(
    db: Session,
    project_id: str,
    work_item_data: ProjectWorkItemCreate,
) -> WorkItem | None:
    """Resolve an external project ID and persist a validated work item."""
    work_id = work_item_data.work_id
    try:
        project = get_project_by_project_id(db, project_id)
        if project is None:
            return None
        if get_work_item_by_work_id(db, work_id) is not None:
            raise DuplicateWorkIdError

        values = work_item_data.model_dump()
        values["labor_total"] = _calculate_labor_total(
            work_item_data.quantity,
            work_item_data.labor_unit_rate,
        )
        work_item = WorkItem(project_id=project.id, **values)
        db.add(work_item)
        db.commit()
        db.refresh(work_item)
        return work_item
    except DuplicateWorkIdError:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        try:
            duplicate = get_work_item_by_work_id(db, work_id)
        except SQLAlchemyError as lookup_exc:
            db.rollback()
            raise WorkItemPersistenceError from lookup_exc
        if duplicate is not None:
            raise DuplicateWorkIdError from exc
        raise WorkItemPersistenceError from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise WorkItemPersistenceError from exc
