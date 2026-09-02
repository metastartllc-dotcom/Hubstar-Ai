import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.main import app
from app.core.database import Base, get_db
from app.models.models import Project, StatusEnum, WorkItem
from app.repositories import work_items as work_items_repository


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = testing_session()
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
        with TestClient(app, raise_server_exceptions=False) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def add_project(db_session, project_id="PRJ-001"):
    project = Project(project_id=project_id, name=f"Project {project_id}")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


def create_work(client, path_project_id="PRJ-001", **overrides):
    payload = {"work_id": "PRJ-001-WRK-001", "name": "Foundation"}
    payload.update(overrides)
    return client.post(f"/api/v1/projects/{path_project_id}/work-items", json=payload)


def test_unknown_project_returns_404_for_list_and_create(client):
    assert client.get("/api/v1/projects/MISSING/work-items").status_code == 404
    assert create_work(client, "MISSING").status_code == 404


def test_empty_project_work_item_list(client, db_session):
    add_project(db_session)
    response = client.get("/api/v1/projects/PRJ-001/work-items")
    assert response.status_code == 200
    assert response.json() == []


def test_minimal_create_uses_external_project_and_hides_internal_fk(client, db_session):
    project = add_project(db_session)
    response = create_work(client)
    assert response.status_code == 201
    body = response.json()
    assert body["work_id"] == "PRJ-001-WRK-001"
    assert body["name"] == "Foundation"
    assert body["status"] == "ACTIVE"
    assert body["labor_total"] is None
    assert "project_id" not in body
    stored = db_session.query(WorkItem).filter_by(work_id=body["work_id"]).one()
    assert stored.project_id == project.id


def test_full_create_calculates_half_up_labor_total(client, db_session):
    add_project(db_session)
    response = create_work(
        client,
        wbs_code=" 1.2 ",
        unit=" m2 ",
        quantity=10.005,
        labor_unit_rate=1,
        status="VALID",
    )
    assert response.status_code == 201
    assert response.json() == {
        "id": 1,
        "work_id": "PRJ-001-WRK-001",
        "name": "Foundation",
        "wbs_code": "1.2",
        "unit": "м²",
        "quantity": 10.005,
        "labor_unit_rate": 1.0,
        "labor_total": 10.01,
        "status": "VALID",
    }


def test_project_isolation_pagination_and_stable_id_order(client, db_session):
    first = add_project(db_session, "PRJ-001")
    second = add_project(db_session, "PRJ-002")
    db_session.add_all([
        WorkItem(work_id="W-1", name="One", project_id=first.id),
        WorkItem(work_id="W-X", name="Other", project_id=second.id),
        WorkItem(work_id="W-2", name="Two", project_id=first.id),
        WorkItem(work_id="W-3", name="Three", project_id=first.id),
    ])
    db_session.commit()
    response = client.get(
        "/api/v1/projects/PRJ-001/work-items", params={"offset": 1, "limit": 2}
    )
    assert response.status_code == 200
    assert [item["work_id"] for item in response.json()] == ["W-2", "W-3"]


@pytest.mark.parametrize(
    "query",
    ["offset=-1", "limit=0", "limit=101"],
)
def test_pagination_validation(client, db_session, query):
    add_project(db_session)
    response = client.get(f"/api/v1/projects/PRJ-001/work-items?{query}")
    assert response.status_code == 422


@pytest.mark.parametrize("field", ["work_id", "name"])
def test_required_string_missing_empty_or_whitespace_is_422(client, db_session, field):
    add_project(db_session)
    valid = {"work_id": "W-1", "name": "Work"}
    for value in (None, "", "   "):
        payload = valid.copy()
        if value is None:
            payload.pop(field)
        else:
            payload[field] = value
        assert client.post("/api/v1/projects/PRJ-001/work-items", json=payload).status_code == 422


@pytest.mark.parametrize("field", ["id", "project_id", "labor_total", "surprise"])
def test_forbidden_and_unknown_fields_are_422(client, db_session, field):
    add_project(db_session)
    response = create_work(client, **{field: 1})
    assert response.status_code == 422


@pytest.mark.parametrize("field", ["quantity", "labor_unit_rate"])
@pytest.mark.parametrize("value", [-1, "NaN", "Infinity", "-Infinity"])
def test_invalid_numbers_are_422(client, db_session, field, value):
    add_project(db_session)
    response = create_work(client, **{field: value})
    assert response.status_code == 422


def test_unit_and_identifiers_are_trimmed_and_unknown_unit_is_preserved(client, db_session):
    add_project(db_session)
    response = create_work(
        client,
        work_id="  W-TRIM  ",
        name="  Trimmed  ",
        wbs_code="  3.1  ",
        unit="  custom-unit  ",
    )
    assert response.status_code == 201
    assert response.json()["work_id"] == "W-TRIM"
    assert response.json()["name"] == "Trimmed"
    assert response.json()["wbs_code"] == "3.1"
    assert response.json()["unit"] == "custom-unit"


@pytest.mark.parametrize("field", ["wbs_code", "unit"])
def test_optional_string_rejects_whitespace(client, db_session, field):
    add_project(db_session)
    assert create_work(client, **{field: "   "}).status_code == 422


def test_invalid_status_is_422(client, db_session):
    add_project(db_session)
    assert create_work(client, status="NOT_A_STATUS").status_code == 422


def test_duplicate_and_trimmed_duplicate_are_409_and_session_recovers(client, db_session):
    add_project(db_session)
    assert create_work(client, work_id="W-DUP").status_code == 201
    duplicate = create_work(client, work_id="  W-DUP  ")
    assert duplicate.status_code == 409
    assert duplicate.json() == {"detail": "Work ID already exists"}
    assert create_work(client, work_id="W-AFTER").status_code == 201


def test_integrity_error_rolls_back_before_confirming_duplicate(
    client, db_session, monkeypatch
):
    add_project(db_session)
    events = []
    lookup_results = iter([None, WorkItem(work_id="W-RACE", name="Competing")])
    real_rollback = db_session.rollback

    def lookup(*args, **kwargs):
        events.append("lookup")
        return next(lookup_results)

    def failing_commit():
        events.append("commit")
        raise IntegrityError("INSERT", {}, Exception("unique constraint"))

    def tracking_rollback():
        events.append("rollback")
        real_rollback()

    monkeypatch.setattr(work_items_repository, "get_work_item_by_work_id", lookup)
    monkeypatch.setattr(db_session, "commit", failing_commit)
    monkeypatch.setattr(db_session, "rollback", tracking_rollback)
    response = create_work(client, work_id="W-RACE")
    assert response.status_code == 409
    assert events == ["lookup", "commit", "rollback", "lookup"]


def test_integrity_error_without_persisted_work_id_is_generic_500(
    client, db_session, monkeypatch
):
    add_project(db_session)
    monkeypatch.setattr(
        work_items_repository,
        "get_work_item_by_work_id",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        db_session,
        "commit",
        lambda: (_ for _ in ()).throw(
            IntegrityError("INSERT internal SQL", {}, Exception("constraint detail"))
        ),
    )
    response = create_work(client, work_id="W-NOT-DUP")
    assert response.status_code == 500
    assert response.json() == {"detail": "Unable to create work item"}
    assert "internal SQL" not in response.text
    assert "constraint detail" not in response.text


def test_other_database_error_rolls_back_and_returns_generic_500(
    client, db_session, monkeypatch
):
    add_project(db_session)
    rollback_calls = 0
    real_rollback = db_session.rollback

    def tracking_rollback():
        nonlocal rollback_calls
        rollback_calls += 1
        real_rollback()

    def failing_commit():
        raise OperationalError("INSERT secret SQL", {}, Exception("database detail"))

    monkeypatch.setattr(db_session, "rollback", tracking_rollback)
    monkeypatch.setattr(db_session, "commit", failing_commit)
    response = create_work(client)
    assert response.status_code == 500
    assert response.json() == {"detail": "Unable to create work item"}
    assert rollback_calls == 1
    assert "SQL" not in response.text
    assert "database detail" not in response.text


def test_created_work_item_is_visible_via_get(client, db_session):
    add_project(db_session)
    assert create_work(client).status_code == 201
    response = client.get("/api/v1/projects/PRJ-001/work-items")
    assert response.status_code == 200
    assert [item["work_id"] for item in response.json()] == ["PRJ-001-WRK-001"]
