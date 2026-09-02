import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.main import app
from app.core.database import Base, get_db
from app.models.models import Project, StatusEnum
from app.repositories import projects as projects_repository
from app.repositories.projects import (
    DuplicateProjectIdError,
    ProjectCreationError,
)
from app.schemas.schemas import ProjectCreate


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


def test_create_project_returns_201_and_response(client):
    response = client.post(
        "/api/v1/projects",
        json={
            "project_id": "  PRJ-CREATE-001  ",
            "name": "  New project  ",
            "location": "  Ulaanbaatar  ",
            "project_type": "  Residential  ",
            "gross_floor_area": 1250.5,
            "start_date": "2026-09-01",
            "end_date": "2027-09-01",
            "status": "ACTIVE",
        },
    )

    assert response.status_code == 201
    assert response.json() == {
        "id": 1,
        "project_id": "PRJ-CREATE-001",
        "name": "New project",
        "location": "Ulaanbaatar",
        "project_type": "Residential",
        "gross_floor_area": 1250.5,
        "start_date": "2026-09-01",
        "end_date": "2027-09-01",
        "status": "ACTIVE",
        "owner_organization_id": None,
        "contractor_organization_id": None,
    }


def test_created_project_appears_in_list_and_detail(client):
    create_response = client.post(
        "/api/v1/projects",
        json={"project_id": "PRJ-CREATE-002", "name": "Listed project"},
    )
    assert create_response.status_code == 201

    list_response = client.get("/api/v1/projects")
    detail_response = client.get("/api/v1/projects/PRJ-CREATE-002")

    assert list_response.status_code == 200
    assert [project["project_id"] for project in list_response.json()] == [
        "PRJ-CREATE-002"
    ]
    assert detail_response.status_code == 200
    assert detail_response.json()["project_id"] == "PRJ-CREATE-002"
    assert detail_response.json()["name"] == "Listed project"


def test_trimmed_project_id_works_in_response_and_detail(client):
    response = client.post(
        "/api/v1/projects",
        json={"project_id": "  PRJ-TRIMMED  ", "name": "  Trimmed project  "},
    )

    assert response.status_code == 201
    assert response.json()["project_id"] == "PRJ-TRIMMED"
    assert response.json()["name"] == "Trimmed project"
    assert client.get("/api/v1/projects/PRJ-TRIMMED").status_code == 200


def test_duplicate_project_id_returns_409_and_session_recovers(client):
    payload = {"project_id": "PRJ-DUPLICATE", "name": "Original project"}
    assert client.post("/api/v1/projects", json=payload).status_code == 201

    duplicate_response = client.post(
        "/api/v1/projects",
        json={"project_id": "PRJ-DUPLICATE", "name": "Duplicate project"},
    )
    recovery_response = client.post(
        "/api/v1/projects",
        json={"project_id": "PRJ-AFTER-DUPLICATE", "name": "Recovered session"},
    )

    assert duplicate_response.status_code == 409
    assert duplicate_response.json() == {"detail": "Project ID already exists"}
    assert recovery_response.status_code == 201
    assert client.get("/api/v1/projects/PRJ-AFTER-DUPLICATE").status_code == 200


def test_duplicate_project_id_after_trimming_returns_409(client):
    assert client.post(
        "/api/v1/projects",
        json={"project_id": "PRJ-TRIM-DUP", "name": "Original"},
    ).status_code == 201

    response = client.post(
        "/api/v1/projects",
        json={"project_id": "  PRJ-TRIM-DUP  ", "name": "Duplicate"},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Project ID already exists"}


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "Missing project ID"},
        {"project_id": None, "name": "Null project ID"},
        {"project_id": "PRJ-EMPTY-NAME", "name": ""},
        {"project_id": "PRJ-WHITESPACE-NAME", "name": "   "},
        {"project_id": "", "name": "Project"},
        {"project_id": "   ", "name": "Project"},
    ],
)
def test_create_project_rejects_empty_identifiers(client, payload):
    response = client.post("/api/v1/projects", json=payload)

    assert response.status_code == 422


def test_create_project_rejects_negative_gross_floor_area(client):
    response = client.post(
        "/api/v1/projects",
        json={
            "project_id": "PRJ-NEGATIVE-AREA",
            "name": "Invalid project",
            "gross_floor_area": -1,
        },
    )

    assert response.status_code == 422


def test_integrity_error_rolls_back_before_duplicate_lookup(monkeypatch):
    events = []
    db = type("FakeSession", (), {})()
    db.add = lambda project: events.append("add")

    def fail_commit():
        events.append("commit")
        raise IntegrityError("hidden statement", {}, Exception("hidden database error"))

    db.commit = fail_commit
    db.rollback = lambda: events.append("rollback")
    db.refresh = lambda project: events.append("refresh")
    lookup_results = iter([None, Project(project_id="PRJ-RACE", name="Existing")])

    def lookup(db_arg, project_id):
        events.append("lookup")
        return next(lookup_results)

    monkeypatch.setattr(projects_repository, "get_project_by_project_id", lookup)

    with pytest.raises(DuplicateProjectIdError):
        projects_repository.create_project(
            db,
            ProjectCreate(project_id="PRJ-RACE", name="Race project"),
        )

    assert events == ["lookup", "add", "commit", "rollback", "lookup"]


def test_non_duplicate_integrity_error_is_not_misreported(monkeypatch):
    db = type("FakeSession", (), {})()
    db.add = lambda project: None
    db.commit = lambda: (_ for _ in ()).throw(
        IntegrityError("hidden statement", {}, Exception("hidden database error"))
    )
    db.rollback = lambda: None
    db.refresh = lambda project: None
    monkeypatch.setattr(
        projects_repository,
        "get_project_by_project_id",
        lambda db_arg, project_id: None,
    )

    with pytest.raises(ProjectCreationError):
        projects_repository.create_project(
            db,
            ProjectCreate(project_id="PRJ-INTEGRITY", name="Integrity failure"),
        )


def test_internal_project_creation_error_is_hidden(client, monkeypatch):
    def fail_create(db, project_data):
        raise ProjectCreationError("SQL: hidden internal database detail")

    monkeypatch.setattr("app.api.routes.projects.create_project", fail_create)

    response = client.post(
        "/api/v1/projects",
        json={"project_id": "PRJ-HIDDEN-ERROR", "name": "Hidden error"},
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Unable to create project"}
    assert "SQL" not in response.text
    assert "hidden" not in response.text


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


def test_update_project_fields_and_get_detail(client, db_session):
    add_project(db_session, "PRJ-UPDATE-001", "Original project")

    response = client.patch(
        "/api/v1/projects/PRJ-UPDATE-001",
        json={
            "name": "Updated project",
            "location": "Ulaanbaatar",
            "project_type": "Residential",
            "gross_floor_area": 2400.5,
        },
    )
    detail = client.get("/api/v1/projects/PRJ-UPDATE-001")

    assert response.status_code == 200
    assert response.json()["project_id"] == "PRJ-UPDATE-001"
    assert response.json()["name"] == "Updated project"
    assert response.json()["location"] == "Ulaanbaatar"
    assert response.json()["project_type"] == "Residential"
    assert response.json()["gross_floor_area"] == 2400.5
    assert detail.status_code == 200
    assert detail.json() == response.json()


def test_partial_update_preserves_unspecified_fields(client, db_session):
    project = add_project(db_session, "PRJ-PARTIAL", "Original name")
    project.location = "Original location"
    project.project_type = "Commercial"
    project.gross_floor_area = 1000.0
    project.status = StatusEnum.NEEDS_REVIEW
    db_session.commit()

    response = client.patch(
        "/api/v1/projects/PRJ-PARTIAL",
        json={"name": "Partial update"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Partial update"
    assert response.json()["location"] == "Original location"
    assert response.json()["project_type"] == "Commercial"
    assert response.json()["gross_floor_area"] == 1000.0
    assert response.json()["status"] == "NEEDS_REVIEW"


def test_update_trims_string_fields(client, db_session):
    add_project(db_session, "PRJ-TRIM-UPDATE", "Original")

    response = client.patch(
        "/api/v1/projects/PRJ-TRIM-UPDATE",
        json={
            "name": "  Trimmed name  ",
            "location": "  Ulaanbaatar  ",
            "project_type": "  Residential  ",
        },
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Trimmed name"
    assert response.json()["location"] == "Ulaanbaatar"
    assert response.json()["project_type"] == "Residential"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"unknown_field": "value"},
        {"id": 99},
        {"project_id": "PRJ-CHANGED"},
        {"owner_organization_id": 1},
        {"contractor_organization_id": 1},
    ],
)
def test_update_rejects_empty_unknown_and_forbidden_fields(
    client,
    db_session,
    payload,
):
    add_project(db_session, "PRJ-FORBIDDEN", "Original")

    response = client.patch("/api/v1/projects/PRJ-FORBIDDEN", json=payload)

    assert response.status_code == 422


@pytest.mark.parametrize(
    "payload",
    [
        {"name": ""},
        {"name": "   "},
        {"name": None},
        {"location": ""},
        {"location": "   "},
        {"project_type": ""},
        {"project_type": "   "},
    ],
)
def test_update_rejects_empty_strings(client, db_session, payload):
    add_project(db_session, "PRJ-EMPTY-UPDATE", "Original")

    response = client.patch("/api/v1/projects/PRJ-EMPTY-UPDATE", json=payload)

    assert response.status_code == 422


def test_update_allows_clearing_optional_strings(client, db_session):
    project = add_project(db_session, "PRJ-CLEAR-OPTIONAL", "Original")
    project.location = "Old location"
    project.project_type = "Old type"
    db_session.commit()

    response = client.patch(
        "/api/v1/projects/PRJ-CLEAR-OPTIONAL",
        json={"location": None, "project_type": None},
    )

    assert response.status_code == 200
    assert response.json()["location"] is None
    assert response.json()["project_type"] is None


@pytest.mark.parametrize(
    "payload",
    [
        {"gross_floor_area": -1},
        {"status": "UNKNOWN"},
        {"status": None},
        {"start_date": "2027-01-02", "end_date": "2027-01-01"},
    ],
)
def test_update_rejects_invalid_values(client, db_session, payload):
    add_project(db_session, "PRJ-INVALID-UPDATE", "Original")

    response = client.patch("/api/v1/projects/PRJ-INVALID-UPDATE", json=payload)

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("payload", "start_date", "end_date"),
    [
        ({"start_date": "2027-01-02"}, "2026-01-01", "2027-01-01"),
        ({"end_date": "2025-12-31"}, "2026-01-01", "2027-01-01"),
    ],
)
def test_update_validates_against_existing_dates(
    client,
    db_session,
    payload,
    start_date,
    end_date,
):
    project = add_project(db_session, "PRJ-DATE-UPDATE", "Original")
    project.start_date = __import__("datetime").date.fromisoformat(start_date)
    project.end_date = __import__("datetime").date.fromisoformat(end_date)
    db_session.commit()

    response = client.patch("/api/v1/projects/PRJ-DATE-UPDATE", json=payload)

    assert response.status_code == 422
    assert response.json() == {
        "detail": "start_date must be on or before end_date"
    }


def test_update_status(client, db_session):
    add_project(db_session, "PRJ-STATUS-UPDATE", "Original")

    response = client.patch(
        "/api/v1/projects/PRJ-STATUS-UPDATE",
        json={"status": "NEEDS_REVIEW"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "NEEDS_REVIEW"


def test_update_unknown_project_returns_404(client):
    response = client.patch(
        "/api/v1/projects/UNKNOWN",
        json={"name": "Updated"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Project not found"}


def test_update_database_error_rolls_back_and_hides_details(
    client,
    db_session,
    monkeypatch,
):
    add_project(db_session, "PRJ-UPDATE-ERROR", "Original")
    rollback_called = False
    original_rollback = db_session.rollback

    def fail_commit():
        raise projects_repository.SQLAlchemyError("SQL: hidden update failure")

    def track_rollback():
        nonlocal rollback_called
        rollback_called = True
        original_rollback()

    monkeypatch.setattr(db_session, "commit", fail_commit)
    monkeypatch.setattr(db_session, "rollback", track_rollback)

    response = client.patch(
        "/api/v1/projects/PRJ-UPDATE-ERROR",
        json={"name": "Should not persist"},
    )

    assert rollback_called is True
    assert response.status_code == 500
    assert response.json() == {"detail": "Unable to update project"}
    assert "SQL" not in response.text
    assert "hidden" not in response.text
