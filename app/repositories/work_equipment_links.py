"""Persistence and snapshot rules for equipment assigned to work items."""
import math
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from app.models.models import Equipment, Project, StatusEnum, WorkEquipmentLink, WorkItem
from app.schemas.schemas import WorkEquipmentCreateRequest, WorkEquipmentUpdateRequest
from app.services.equipment_calculator import calculate_equipment_total


class WorkEquipmentNotFoundError(Exception): pass
class DuplicateWorkEquipmentError(Exception): pass
class WorkEquipmentValidationError(Exception): pass
class InvalidEquipmentConfigurationError(Exception): pass
class WorkEquipmentPersistenceError(Exception): pass

_STATUS_PRIORITY = {
    StatusEnum.VALID: 0, StatusEnum.ACTIVE: 1,
    StatusEnum.ACTIVE_WITH_WARNINGS: 2, StatusEnum.NEEDS_REVIEW: 3,
    StatusEnum.REJECTED: 4, StatusEnum.SUPERSEDED: 5,
}


def effective_link_status(requested: StatusEnum, master: StatusEnum | None) -> StatusEnum:
    """Do not hide a master warning or review state with a safer link state."""
    master = master or StatusEnum.ACTIVE
    return master if _STATUS_PRIORITY[master] > _STATUS_PRIORITY[requested] else requested


def _resolve(db, project_id, work_id):
    project = db.query(Project).filter(Project.project_id == project_id).first()
    if project is None: raise WorkEquipmentNotFoundError
    work = db.query(WorkItem).filter(WorkItem.work_id == work_id, WorkItem.project_id == project.id).first()
    if work is None: raise WorkEquipmentNotFoundError
    return work


def _equipment(db, equipment_id):
    value = db.query(Equipment).filter(Equipment.equipment_id == equipment_id).first()
    if value is None: raise WorkEquipmentNotFoundError
    return value


def _public(link, equipment):
    total = calculate_equipment_total(link.usage_quantity, link.agreed_unit_rate)
    return {"equipment_id": equipment.equipment_id, "type": equipment.type, "capacity": equipment.capacity,
            "usage_quantity": link.usage_quantity, "agreed_unit_rate": link.agreed_unit_rate,
            "tariff_type": link.tariff_type_snapshot, "operator_included": link.operator_included_snapshot,
            "fuel_included": link.fuel_included_snapshot, "delivery_included": link.delivery_included_snapshot,
            "included_delivery_one_way_distance_km": link.included_delivery_one_way_distance_km_snapshot,
            "equipment_total": float(total) if total is not None else None, "status": link.status}


def _validate(rate, tariff, delivery, distance, error_type=WorkEquipmentValidationError):
    if any(value is not None and (not math.isfinite(value) or value < 0)
           for value in (rate, distance)):
        raise error_type
    if rate is not None and (tariff is None or not tariff.strip()):
        raise error_type
    if distance is not None and delivery is not True:
        raise error_type


def list_work_equipment_links(db: Session, project_id: str, work_id: str):
    try:
        work = _resolve(db, project_id, work_id)
        rows = (db.query(WorkEquipmentLink, Equipment).join(Equipment, Equipment.id == WorkEquipmentLink.equipment_id)
                .filter(WorkEquipmentLink.work_item_id == work.id).order_by(WorkEquipmentLink.id).all())
        return [_public(link, equipment) for link, equipment in rows]
    except WorkEquipmentNotFoundError: raise
    except SQLAlchemyError as exc:
        db.rollback(); raise WorkEquipmentPersistenceError from exc


def create_work_equipment_link(db: Session, project_id: str, work_id: str, request: WorkEquipmentCreateRequest):
    work = equipment = None
    try:
        work = _resolve(db, project_id, work_id); equipment = _equipment(db, request.equipment_id)
        if equipment.status in (StatusEnum.REJECTED, StatusEnum.SUPERSEDED):
            raise InvalidEquipmentConfigurationError
        if db.query(WorkEquipmentLink).filter_by(work_item_id=work.id, equipment_id=equipment.id).first():
            raise DuplicateWorkEquipmentError
        _validate(equipment.unit_rate, equipment.tariff_type, equipment.delivery_included,
                  equipment.included_delivery_one_way_distance_km, InvalidEquipmentConfigurationError)
        link = WorkEquipmentLink(work_item_id=work.id, equipment_id=equipment.id,
            usage_quantity=request.usage_quantity, agreed_unit_rate=equipment.unit_rate,
            tariff_type_snapshot=equipment.tariff_type, operator_included_snapshot=equipment.operator_included,
            fuel_included_snapshot=equipment.fuel_included, delivery_included_snapshot=equipment.delivery_included,
            included_delivery_one_way_distance_km_snapshot=equipment.included_delivery_one_way_distance_km,
            status=effective_link_status(request.status, equipment.status))
        db.add(link); db.commit(); db.refresh(link); return _public(link, equipment)
    except (WorkEquipmentNotFoundError, DuplicateWorkEquipmentError, WorkEquipmentValidationError,
            InvalidEquipmentConfigurationError):
        db.rollback(); raise
    except IntegrityError as exc:
        db.rollback()
        try:
            duplicate = work and equipment and db.query(WorkEquipmentLink).filter_by(work_item_id=work.id, equipment_id=equipment.id).first()
        except SQLAlchemyError as lookup_exc:
            db.rollback(); raise WorkEquipmentPersistenceError from lookup_exc
        if duplicate: raise DuplicateWorkEquipmentError from exc
        raise WorkEquipmentPersistenceError from exc
    except SQLAlchemyError as exc:
        db.rollback(); raise WorkEquipmentPersistenceError from exc


def update_work_equipment_link(db: Session, project_id: str, work_id: str, equipment_id: str,
                               request: WorkEquipmentUpdateRequest):
    try:
        work = _resolve(db, project_id, work_id); equipment = _equipment(db, equipment_id)
        link = db.query(WorkEquipmentLink).filter_by(work_item_id=work.id, equipment_id=equipment.id).first()
        if link is None: raise WorkEquipmentNotFoundError
        values = request.model_dump(exclude_unset=True)
        mapping = {"tariff_type":"tariff_type_snapshot", "operator_included":"operator_included_snapshot",
                   "fuel_included":"fuel_included_snapshot", "delivery_included":"delivery_included_snapshot",
                   "included_delivery_one_way_distance_km":"included_delivery_one_way_distance_km_snapshot"}
        proposed = {mapping.get(k,k):v for k,v in values.items()}
        rate = proposed.get("agreed_unit_rate", link.agreed_unit_rate)
        tariff = proposed.get("tariff_type_snapshot", link.tariff_type_snapshot)
        delivery = proposed.get("delivery_included_snapshot", link.delivery_included_snapshot)
        distance = proposed.get("included_delivery_one_way_distance_km_snapshot", link.included_delivery_one_way_distance_km_snapshot)
        _validate(rate, tariff, delivery, distance)
        for field, value in proposed.items(): setattr(link, field, value)
        db.commit(); db.refresh(link); return _public(link, equipment)
    except (WorkEquipmentNotFoundError, WorkEquipmentValidationError):
        db.rollback(); raise
    except SQLAlchemyError as exc:
        db.rollback(); raise WorkEquipmentPersistenceError from exc
