"""Database access for projects."""

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.models import Project
from app.schemas.schemas import ProjectCreate


class DuplicateProjectIdError(Exception):
    """Raised when a project's external identifier already exists."""


class ProjectCreationError(Exception):
    """Raised when a project cannot be persisted."""


def list_projects(db: Session, offset: int, limit: int) -> list[Project]:
    """Return projects ordered consistently for pagination."""
    return db.query(Project).order_by(Project.id).offset(offset).limit(limit).all()


def get_project_by_project_id(db: Session, project_id: str) -> Project | None:
    """Return a project by its external project identifier."""
    return db.query(Project).filter(Project.project_id == project_id).first()


def create_project(db: Session, project_data: ProjectCreate) -> Project:
    """Create and persist a project from validated request data."""
    project_id = project_data.project_id

    try:
        if project_id is not None and get_project_by_project_id(db, project_id):
            raise DuplicateProjectIdError

        project = Project(**project_data.model_dump())
        db.add(project)
        db.commit()
        db.refresh(project)
        return project
    except DuplicateProjectIdError:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        try:
            duplicate_project = get_project_by_project_id(db, project_id)
        except SQLAlchemyError as lookup_exc:
            db.rollback()
            raise ProjectCreationError from lookup_exc
        if duplicate_project is not None:
            raise DuplicateProjectIdError from exc
        raise ProjectCreationError from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise ProjectCreationError from exc
