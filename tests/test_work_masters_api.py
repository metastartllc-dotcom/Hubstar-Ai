import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.main import app
from app.core.database import Base, get_db
from app.models.models import WorkMaster


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def client(db_session):
    def override():
        yield db_session
    app.dependency_overrides[get_db] = override
    try:
        with TestClient(app, raise_server_exceptions=False) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def payload(**updates):
    value = {"work_master_id": "WKM-000001", "name": " Суурийн ажил "}
    value.update(updates)
    return value


def test_empty_list_and_minimal_create_hides_internal_id(client, db_session):
    assert client.get("/api/v1/work-masters").json() == []
    response = client.post("/api/v1/work-masters", json=payload())
    assert response.status_code == 201
    assert response.json() == {
        "work_master_id": "WKM-000001", "name": "Суурийн ажил",
        "category": None, "default_unit": None, "default_labor_unit_rate": None,
        "status": "ACTIVE", "source_dataset": None, "source_work_id": None,
    }
    assert "id" not in response.json()
    assert db_session.query(WorkMaster).one().id == 1


def test_full_create_list_detail_normalization_and_stable_pagination(client):
    first = client.post("/api/v1/work-masters", json=payload(
        category=" Бүтээц ", default_unit=" m2 ", default_labor_unit_rate=1250,
        source_dataset=" HUBSTAR_6R_7R_UNIFIED_2026 ", source_work_id=" WRK-ALTAI-B-001 ",
        status="VALID",
    ))
    assert first.status_code == 201
    assert first.json()["default_unit"] == "м²"
    assert first.json()["category"] == "Бүтээц"
    assert client.post("/api/v1/work-masters", json=payload(
        work_master_id="WKM-000002", name="Second"
    )).status_code == 201
    assert client.get("/api/v1/work-masters/WKM-000001").json() == first.json()
    listed = client.get("/api/v1/work-masters?offset=1&limit=1").json()
    assert [row["work_master_id"] for row in listed] == ["WKM-000002"]


@pytest.mark.parametrize("query", ["offset=-1", "limit=0", "limit=101"])
def test_pagination_validation(client, query):
    assert client.get(f"/api/v1/work-masters?{query}").status_code == 422


@pytest.mark.parametrize("field", ["work_master_id", "name"])
@pytest.mark.parametrize("value", [None, "", "   "])
def test_required_strings(client, field, value):
    request = payload(**{field: value})
    assert client.post("/api/v1/work-masters", json=request).status_code == 422


def test_source_pair_and_numeric_validation(client):
    for request in (
        payload(source_dataset="D"), payload(source_work_id="W"),
        payload(default_labor_unit_rate=-1), payload(default_labor_unit_rate="NaN"),
        payload(extra="no"),
        payload(work_master_id="WRK-ALTAI-B-001"),
        payload(work_master_id="WKM-1"),
    ):
        assert client.post("/api/v1/work-masters", json=request).status_code == 422


def test_duplicate_id_and_source_pair_are_409_and_session_recovers(client):
    complete = payload(source_dataset="D", source_work_id="W")
    assert client.post("/api/v1/work-masters", json=complete).status_code == 201
    assert client.post("/api/v1/work-masters", json=complete).status_code == 409
    duplicate_source = payload(work_master_id="WKM-000002", source_dataset="D", source_work_id="W")
    assert client.post("/api/v1/work-masters", json=duplicate_source).status_code == 409
    assert client.get("/api/v1/work-masters").status_code == 200


def test_unknown_detail_and_openapi_boundary(client):
    assert client.get("/api/v1/work-masters/MISSING").status_code == 404
    schema = client.get("/openapi.json").json()
    response = schema["components"]["schemas"]["WorkMasterPublicResponse"]["properties"]
    assert "id" not in response
    assert "/api/v1/work-masters" in schema["paths"]


def test_create_all_source_pair_check_rejects_partial_orm_data(db_session):
    db_session.add(WorkMaster(
        work_master_id="WKM-000001", name="Bad", source_dataset="D",
    ))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
    db_session.add(WorkMaster(work_master_id="WKM-000002", name="Good"))
    db_session.commit()
    assert db_session.query(WorkMaster).count() == 1


def test_database_error_rolls_back_and_returns_generic_500(client, db_session, monkeypatch):
    events = []
    real_rollback = db_session.rollback

    def fail_commit():
        events.append("error")
        raise OperationalError("secret SQL", {}, Exception("internal secret"))

    def tracked_rollback():
        events.append("rollback")
        real_rollback()

    with monkeypatch.context() as patch:
        patch.setattr(db_session, "commit", fail_commit)
        patch.setattr(db_session, "rollback", tracked_rollback)
        response = client.post("/api/v1/work-masters", json=payload())
    assert response.status_code == 500
    assert response.json() == {"detail": "Unable to create work master"}
    assert events == ["error", "rollback"]
    assert "secret" not in response.text.lower() and "sql" not in response.text.lower()
    assert client.post("/api/v1/work-masters", json=payload()).status_code == 201
