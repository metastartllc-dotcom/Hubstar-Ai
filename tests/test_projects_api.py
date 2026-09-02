import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.main import app
from app.core.database import Base, get_db
from app.models.models import Project, StatusEnum


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def add_project(db_session, project_id: str, name: str) -> Project:
    project = Project(
        project_id=project_id,
        name=name,
        status=StatusEnum.ACTIVE,
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


def test_empty_project_list(client):
    response = client.get("/api/v1/projects")

    assert response.status_code == 200
    assert response.json() == []


def test_project_list_returns_projects(client, db_session):
    add_project(db_session, "PRJ-001", "First project")

    response = client.get("/api/v1/projects")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["project_id"] == "PRJ-001"
    assert response.json()[0]["name"] == "First project"


def test_project_list_pagination(client, db_session):
    add_project(db_session, "PRJ-001", "First project")
    add_project(db_session, "PRJ-002", "Second project")
    add_project(db_session, "PRJ-003", "Third project")

    response = client.get("/api/v1/projects", params={"offset": 1, "limit": 1})

    assert response.status_code == 200
    assert [project["project_id"] for project in response.json()] == ["PRJ-002"]


def test_project_detail_uses_external_project_id(client, db_session):
    add_project(db_session, "PRJ-EXT-001", "External ID project")

    response = client.get("/api/v1/projects/PRJ-EXT-001")

    assert response.status_code == 200
    assert response.json()["project_id"] == "PRJ-EXT-001"
    assert response.json()["name"] == "External ID project"


def test_unknown_project_returns_404(client):
    response = client.get("/api/v1/projects/UNKNOWN")

    assert response.status_code == 404
    assert response.json() == {"detail": "Project not found"}


@pytest.mark.parametrize(
    ("params", "invalid_field"),
    [
        ({"offset": -1}, "offset"),
        ({"limit": 0}, "limit"),
        ({"limit": 101}, "limit"),
    ],
)
def test_project_list_validates_pagination(client, params, invalid_field):
    response = client.get("/api/v1/projects", params=params)

    assert response.status_code == 422
    assert invalid_field in response.text
