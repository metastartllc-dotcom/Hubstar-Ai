"""Database access for projects."""

from sqlalchemy.orm import Session

from app.models.models import Project


def list_projects(db: Session, offset: int, limit: int) -> list[Project]:
    """Return projects ordered consistently for pagination."""
    return db.query(Project).order_by(Project.id).offset(offset).limit(limit).all()


def get_project_by_project_id(db: Session, project_id: str) -> Project | None:
    """Return a project by its external project identifier."""
    return db.query(Project).filter(Project.project_id == project_id).first()
