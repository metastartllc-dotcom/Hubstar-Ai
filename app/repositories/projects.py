"""Database access for projects."""

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.models import Project
from app.schemas.schemas import ProjectCreate, ProjectUpdate


class DuplicateProjectIdError(Exception):
    """Raised when a project's external identifier already exists."""


class ProjectCreationError(Exception):
    """Raised when a project cannot be persisted."""


class ProjectUpdateError(Exception):
    """Raised when a project update cannot be persisted."""


class InvalidProjectDateRangeError(Exception):
    """Raised when the effective project date range is invalid."""


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


def update_project(
    db: Session,
    project_id: str,
    project_data: ProjectUpdate,
) -> Project | None:
    """Update only fields explicitly supplied for an external project ID."""
    try:
        project = get_project_by_project_id(db, project_id)
        if project is None:
            return None

        update_values = project_data.model_dump(exclude_unset=True)
        effective_start_date = update_values.get("start_date", project.start_date)
        effective_end_date = update_values.get("end_date", project.end_date)
        if (
            effective_start_date is not None
            and effective_end_date is not None
            and effective_start_date > effective_end_date
        ):
            db.rollback()
            raise InvalidProjectDateRangeError

        for field_name, value in update_values.items():
            setattr(project, field_name, value)

        db.commit()
        db.refresh(project)
        return project
    except InvalidProjectDateRangeError:
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise ProjectUpdateError from exc
