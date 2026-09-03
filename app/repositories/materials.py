"""Database access for global material master data."""

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.models import Material
from app.schemas.schemas import MaterialCreateRequest


class DuplicateMaterialIdError(Exception):
    """Raised when a material external identifier already exists."""


class MaterialPersistenceError(Exception):
    """Raised when a material database operation fails."""


def _find_material(db: Session, material_id: str) -> Material | None:
    return db.query(Material).filter(Material.material_id == material_id).first()


def list_materials(db: Session, offset: int, limit: int) -> list[Material]:
    """Return materials in stable database ID order."""
    try:
        return db.query(Material).order_by(Material.id).offset(offset).limit(limit).all()
    except SQLAlchemyError as exc:
        raise MaterialPersistenceError from exc


def get_material_by_material_id(db: Session, material_id: str) -> Material | None:
    """Return a material by its global external identifier."""
    try:
        return _find_material(db, material_id)
    except SQLAlchemyError as exc:
        raise MaterialPersistenceError from exc


def create_material(
    db: Session,
    material_data: MaterialCreateRequest,
) -> Material:
    """Persist validated global material master data."""
    material_id = material_data.material_id
    try:
        if _find_material(db, material_id) is not None:
            raise DuplicateMaterialIdError

        material = Material(**material_data.model_dump())
        db.add(material)
        db.commit()
        db.refresh(material)
        return material
    except DuplicateMaterialIdError:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        try:
            duplicate = _find_material(db, material_id)
        except SQLAlchemyError as lookup_exc:
            db.rollback()
            raise MaterialPersistenceError from lookup_exc
        if duplicate is not None:
            raise DuplicateMaterialIdError from exc
        raise MaterialPersistenceError from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise MaterialPersistenceError from exc
