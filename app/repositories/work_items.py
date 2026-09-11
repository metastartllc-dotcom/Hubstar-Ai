"""Database access for project work items."""

from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.models import StatusEnum, WorkItem
from app.repositories.work_masters import get_work_master_by_work_master_id
from app.repositories.projects import get_project_by_project_id
from app.schemas.schemas import ProjectWorkItemCreate, ProjectWorkItemFromMasterCreate, WorkItemUpdateRequest


class DuplicateWorkIdError(Exception):
    """Raised when a global external work identifier already exists."""


class WorkItemPersistenceError(Exception):
    """Raised when a work item database operation fails."""


class WorkMasterNotFoundError(Exception):
    """Raised when a requested external work master does not exist."""


class InvalidWorkMasterStatusError(Exception):
    """Raised when a work master cannot safely instantiate project work."""


_STATUS_PRIORITY = {
    StatusEnum.VALID: 0,
    StatusEnum.ACTIVE: 1,
    StatusEnum.ACTIVE_WITH_WARNINGS: 2,
    StatusEnum.NEEDS_REVIEW: 3,
    StatusEnum.REJECTED: 4,
    StatusEnum.SUPERSEDED: 5,
}


def _effective_work_status(requested: StatusEnum, master: StatusEnum) -> StatusEnum:
    return master if _STATUS_PRIORITY[master] > _STATUS_PRIORITY[requested] else requested


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


def create_work_item_from_master(
    db: Session,
    project_id: str,
    request: ProjectWorkItemFromMasterCreate,
) -> WorkItem | None:
    """Snapshot master defaults into a project-owned work item."""
    work_id = request.work_id
    try:
        project = get_project_by_project_id(db, project_id)
        if project is None:
            return None
        master = get_work_master_by_work_master_id(db, request.work_master_id)
        if master is None:
            raise WorkMasterNotFoundError
        if master.status in (StatusEnum.REJECTED, StatusEnum.SUPERSEDED):
            raise InvalidWorkMasterStatusError
        if get_work_item_by_work_id(db, work_id) is not None:
            raise DuplicateWorkIdError

        supplied = request.model_dump(exclude_unset=True)
        name = supplied.get("name", master.name)
        unit = supplied.get("unit", master.default_unit)
        labor_rate = supplied.get("labor_unit_rate", master.default_labor_unit_rate)
        work = WorkItem(
            project_id=project.id,
            work_master_ref_id=master.id,
            work_id=work_id,
            name=name,
            wbs_code=request.wbs_code,
            unit=unit,
            quantity=request.quantity,
            labor_unit_rate=labor_rate,
            labor_total=_calculate_labor_total(request.quantity, labor_rate),
            status=_effective_work_status(request.status, master.status),
        )
        db.add(work)
        db.commit()
        db.refresh(work)
        return work
    except (DuplicateWorkIdError, WorkMasterNotFoundError, InvalidWorkMasterStatusError):
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
