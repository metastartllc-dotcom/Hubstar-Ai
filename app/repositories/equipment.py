"""Global equipment master persistence without budget side effects."""

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.models import Equipment
from app.schemas.schemas import EquipmentCreateRequest, EquipmentUpdateRequest


class DuplicateEquipmentIdError(Exception):
    """The external equipment identifier already exists."""


class EquipmentPersistenceError(Exception):
    """An equipment database operation failed."""


class EquipmentNotFoundError(Exception):
    """External equipment ID is unknown."""


class EquipmentValidationError(Exception):
    """Merged equipment attributes violate the tariff contract."""


def update_equipment(db: Session, equipment_id: str, update_data: EquipmentUpdateRequest) -> Equipment:
    try:
        equipment = _find(db, equipment_id)
        if equipment is None:
            raise EquipmentNotFoundError
        values = update_data.model_dump(exclude_unset=True)
        rate = values.get("unit_rate", equipment.unit_rate)
        tariff = values.get("tariff_type", equipment.tariff_type)
        if rate is not None and (tariff is None or not tariff.strip()):
            raise EquipmentValidationError
        for field, value in values.items():
            setattr(equipment, field, value)
        db.commit()
        db.refresh(equipment)
        return equipment
    except (EquipmentNotFoundError, EquipmentValidationError):
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise EquipmentPersistenceError from exc


def _find(db: Session, equipment_id: str) -> Equipment | None:
    return db.query(Equipment).filter(Equipment.equipment_id == equipment_id).first()


def list_equipment(db: Session, offset: int, limit: int) -> list[Equipment]:
    try:
        return db.query(Equipment).order_by(Equipment.id).offset(offset).limit(limit).all()
    except SQLAlchemyError as exc:
        db.rollback()
        raise EquipmentPersistenceError from exc


def get_equipment_by_equipment_id(db: Session, equipment_id: str) -> Equipment | None:
    try:
        return _find(db, equipment_id)
    except SQLAlchemyError as exc:
        db.rollback()
        raise EquipmentPersistenceError from exc


def create_equipment(db: Session, request: EquipmentCreateRequest) -> Equipment:
    try:
        if _find(db, request.equipment_id) is not None:
            raise DuplicateEquipmentIdError
        equipment = Equipment(**request.model_dump())
        db.add(equipment)
        db.commit()
        db.refresh(equipment)
        return equipment
    except DuplicateEquipmentIdError:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        try:
            duplicate = _find(db, request.equipment_id)
        except SQLAlchemyError as lookup_exc:
            db.rollback()
            raise EquipmentPersistenceError from lookup_exc
        if duplicate is not None:
            raise DuplicateEquipmentIdError from exc
        raise EquipmentPersistenceError from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise EquipmentPersistenceError from exc
