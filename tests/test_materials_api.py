import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.main import app
from app.core.database import Base, get_db
from app.models.models import Material
from app.repositories import materials as materials_repository


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


def add_material(db_session, material_id="MAT-001", name="Material"):
    material = Material(material_id=material_id, name=name)
    db_session.add(material)
    db_session.commit()
    db_session.refresh(material)
    return material


def create_material(client, **overrides):
    payload = {"material_id": "MAT-001", "name": "Material"}
    payload.update(overrides)
    return client.post("/api/v1/materials", json=payload)


def test_empty_material_list(client):
    response = client.get("/api/v1/materials")
    assert response.status_code == 200
    assert response.json() == []


def test_minimal_create_and_public_response(client):
    response = create_material(client)
    assert response.status_code == 201
    assert response.json() == {
        "material_id": "MAT-001",
        "master_id": None,
        "code": None,
        "name": "Material",
        "specification": None,
        "normalized_unit": None,
        "unit_price": None,
        "status": "ACTIVE",
    }
    assert "id" not in response.json()
    assert "supplier_id" not in response.json()


def test_full_create_normalizes_unit_and_trims_strings(client):
    response = create_material(
        client,
        material_id="  MAT-FULL  ",
        master_id="  MASTER-1  ",
        code="  SKU-1  ",
        name="  Full material  ",
        specification="  Grade A  ",
        normalized_unit="  m2  ",
        unit_price=1250.5,
        status="VALID",
    )
    assert response.status_code == 201
    assert response.json() == {
        "material_id": "MAT-FULL",
        "master_id": "MASTER-1",
        "code": "SKU-1",
        "name": "Full material",
        "specification": "Grade A",
        "normalized_unit": "м²",
        "unit_price": 1250.5,
        "status": "VALID",
    }


def test_list_detail_pagination_and_stable_order(client, db_session):
    add_material(db_session, "MAT-001", "First")
    add_material(db_session, "MAT-002", "Second")
    add_material(db_session, "MAT-003", "Third")
    listing = client.get("/api/v1/materials", params={"offset": 1, "limit": 1})
    detail = client.get("/api/v1/materials/MAT-002")
    assert listing.status_code == 200
    assert [item["material_id"] for item in listing.json()] == ["MAT-002"]
    assert detail.status_code == 200
    assert detail.json()["name"] == "Second"
    assert "id" not in detail.json()
    assert "supplier_id" not in detail.json()


def test_unknown_material_is_404(client):
    response = client.get("/api/v1/materials/UNKNOWN")
    assert response.status_code == 404


@pytest.mark.parametrize("query", ["offset=-1", "limit=0", "limit=101"])
def test_pagination_validation(client, query):
    assert client.get(f"/api/v1/materials?{query}").status_code == 422


@pytest.mark.parametrize("field", ["material_id", "name"])
@pytest.mark.parametrize("case", ["missing", "null", "empty", "whitespace"])
def test_required_strings_reject_missing_null_empty(client, field, case):
    payload = {"material_id": "MAT-001", "name": "Material"}
    if case == "missing":
        payload.pop(field)
    elif case == "null":
        payload[field] = None
    elif case == "empty":
        payload[field] = ""
    else:
        payload[field] = "   "
    assert client.post("/api/v1/materials", json=payload).status_code == 422


@pytest.mark.parametrize(
    "field", ["master_id", "code", "specification", "normalized_unit"]
)
def test_optional_strings_reject_whitespace(client, field):
    assert create_material(client, **{field: "   "}).status_code == 422


@pytest.mark.parametrize("field", ["id", "supplier_id", "unknown"])
def test_forbidden_and_unknown_fields_are_422(client, field):
    assert create_material(client, **{field: 1}).status_code == 422


@pytest.mark.parametrize("value", [-1, "NaN", "Infinity", "-Infinity"])
def test_invalid_unit_price_is_422(client, value):
    assert create_material(client, unit_price=value).status_code == 422


def test_unknown_unit_is_trimmed_and_preserved(client):
    response = create_material(client, normalized_unit="  custom-unit  ")
    assert response.status_code == 201
    assert response.json()["normalized_unit"] == "custom-unit"


def test_duplicate_and_trimmed_duplicate_are_409_and_session_recovers(client):
    assert create_material(client, material_id="MAT-DUP").status_code == 201
    duplicate = create_material(client, material_id="  MAT-DUP  ")
    assert duplicate.status_code == 409
    assert duplicate.json() == {"detail": "Material ID already exists"}
    assert create_material(client, material_id="MAT-AFTER").status_code == 201


def test_integrity_error_rolls_back_before_confirming_duplicate(
    client, db_session, monkeypatch
):
    events = []
    lookup_results = iter([None, Material(material_id="MAT-RACE", name="Competing")])
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

    monkeypatch.setattr(materials_repository, "_find_material", lookup)
    monkeypatch.setattr(db_session, "commit", failing_commit)
    monkeypatch.setattr(db_session, "rollback", tracking_rollback)
    response = create_material(client, material_id="MAT-RACE")
    assert response.status_code == 409
    assert events == ["lookup", "commit", "rollback", "lookup"]


def test_integrity_error_without_duplicate_is_generic_500(
    client, db_session, monkeypatch
):
    monkeypatch.setattr(materials_repository, "_find_material", lambda *args: None)
    monkeypatch.setattr(
        db_session,
        "commit",
        lambda: (_ for _ in ()).throw(
            IntegrityError("INSERT internal SQL", {}, Exception("constraint detail"))
        ),
    )
    response = create_material(client)
    assert response.status_code == 500
    assert response.json() == {"detail": "Unable to create material"}
    assert "internal SQL" not in response.text
    assert "constraint detail" not in response.text


def test_other_database_error_rolls_back_and_is_generic(
    client, db_session, monkeypatch
):
    rollback_calls = 0
    real_rollback = db_session.rollback

    def tracking_rollback():
        nonlocal rollback_calls
        rollback_calls += 1
        real_rollback()

    monkeypatch.setattr(db_session, "rollback", tracking_rollback)
    monkeypatch.setattr(
        db_session,
        "commit",
        lambda: (_ for _ in ()).throw(
            OperationalError("INSERT private SQL", {}, Exception("database detail"))
        ),
    )
    response = create_material(client)
    assert response.status_code == 500
    assert response.json() == {"detail": "Unable to create material"}
    assert rollback_calls == 1
    assert "private SQL" not in response.text
    assert "database detail" not in response.text
