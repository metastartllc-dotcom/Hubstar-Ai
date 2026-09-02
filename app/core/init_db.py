"""Explicit database schema initialization command."""

from app.core.database import Base, engine
from app.models import models  # noqa: F401 - registers ORM models with Base


def init_database() -> None:
    """Create tables registered in the SQLAlchemy metadata."""
    Base.metadata.create_all(bind=engine)


def main() -> None:
    """Initialize the configured database schema."""
    init_database()
    print("Database schema initialized.")


if __name__ == "__main__":
    main()
