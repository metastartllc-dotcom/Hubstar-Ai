"""Persistence boundary for reusable work masters."""

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.models import WorkMaster
from app.schemas.schemas import WorkMasterCreateRequest


class DuplicateWorkMasterIdError(Exception):
    pass


class DuplicateWorkMasterSourceError(Exception):
    pass


class WorkMasterPersistenceError(Exception):
    pass


def list_work_masters(db: Session, offset: int, limit: int) -> list[WorkMaster]:
    try:
        return db.query(WorkMaster).order_by(WorkMaster.id).offset(offset).limit(limit).all()
    except SQLAlchemyError as exc:
        raise WorkMasterPersistenceError from exc


def get_work_master_by_work_master_id(db: Session, work_master_id: str) -> WorkMaster | None:
    return db.query(WorkMaster).filter(WorkMaster.work_master_id == work_master_id).first()


def _get_by_source(db: Session, dataset: str, source_id: str) -> WorkMaster | None:
    return db.query(WorkMaster).filter(
        WorkMaster.source_dataset == dataset,
        WorkMaster.source_work_id == source_id,
    ).first()


def create_work_master(db: Session, request: WorkMasterCreateRequest) -> WorkMaster:
    values = request.model_dump()
    master_id = request.work_master_id
    source_pair = (request.source_dataset, request.source_work_id)
    try:
        if get_work_master_by_work_master_id(db, master_id) is not None:
            raise DuplicateWorkMasterIdError
        if source_pair[0] is not None and _get_by_source(db, source_pair[0], source_pair[1]) is not None:
            raise DuplicateWorkMasterSourceError
        master = WorkMaster(**values)
        db.add(master)
        db.commit()
        db.refresh(master)
        return master
    except (DuplicateWorkMasterIdError, DuplicateWorkMasterSourceError):
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        try:
            if get_work_master_by_work_master_id(db, master_id) is not None:
                raise DuplicateWorkMasterIdError from exc
            if source_pair[0] is not None and _get_by_source(db, source_pair[0], source_pair[1]) is not None:
                raise DuplicateWorkMasterSourceError from exc
        except (DuplicateWorkMasterIdError, DuplicateWorkMasterSourceError):
            raise
        except SQLAlchemyError as lookup_exc:
            db.rollback()
            raise WorkMasterPersistenceError from lookup_exc
        raise WorkMasterPersistenceError from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise WorkMasterPersistenceError from exc
