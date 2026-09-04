import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.main import app
from app.core.database import Base, get_db
from app.models.models import Material, Project, WorkItem, WorkMaterialLink


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


def seed(db, *, project_id="PRJ-1", work_id="WRK-1", quantity=10, material_id="MAT-1", price=None):
    project = Project(project_id=project_id, name=project_id)
    db.add(project)
    db.commit()
    db.refresh(project)
    work = WorkItem(work_id=work_id, project_id=project.id, name=work_id, quantity=quantity)
    material = Material(
        material_id=material_id,
        name=material_id,
        normalized_unit="кг",
        unit_price=price,
    )
    db.add_all([work, material])
    db.commit()
    db.refresh(work)
    db.refresh(material)
    return project, work, material


def url(project="PRJ-1", work="WRK-1"):
    return f"/api/v1/projects/{project}/work-items/{work}/materials"


def create_link(client, project="PRJ-1", work="WRK-1", **overrides):
    payload = {"material_id": "MAT-1", "consumption_rate": 1}
    payload.update(overrides)
    return client.post(url(project, work), json=payload)


def test_patch_flow_and_summary(client, db_session):
    _, work, _ = seed(db_session, price=2)
    work.labor_total = 100
    db_session.commit()
    assert create_link(client, status="NEEDS_REVIEW").status_code == 201
    endpoint = url() + "/MAT-1"
    response = client.patch(endpoint, json={"consumption_rate": 2})
    assert response.status_code == 200
    assert response.json()["calculated_quantity"] == 20
    assert response.json()["status"] == "NEEDS_REVIEW"
    assert db_session.query(WorkMaterialLink).one().calculated_quantity == 20
    response = client.patch(endpoint, json={"waste_percentage": 10})
    assert response.json()["calculated_quantity"] == 22
    assert response.json()["consumption_rate"] == 2
    for approved, effective, total in [(7.7777, 7.778, 15.56), (0, 0, 0), (None, 22, 44)]:
        response = client.patch(endpoint, json={"approved_quantity": approved})
        assert response.status_code == 200
        assert response.json()["effective_quantity"] == effective
        assert response.json()["material_total"] == total
        summary = client.get("/api/v1/projects/PRJ-1/work-items/WRK-1/summary").json()
        assert summary["material_subtotal_known"] == total
    response = client.patch(endpoint, json={"status": "ACTIVE"})
    assert response.status_code == 200
    assert response.json()["calculated_quantity"] == 22
    assert not {"id", "work_id", "project_id"}.intersection(response.json())
    summary = client.get("/api/v1/projects/PRJ-1/work-items/WRK-1/summary").json()
    assert summary["needs_review_count"] == 0
    assert summary["subtotal_known_before_vat"] == 144


@pytest.mark.parametrize("payload", [
    {}, {"consumption_rate": None}, {"waste_percentage": None},
    {"status": None}, {"status": "INVALID"},
    *[{key: 1} for key in ("id", "project_id", "work_id", "material_id",
       "calculated_quantity", "effective_quantity", "material_total", "unit_price", "unknown")],
    *[{key: value} for key in ("consumption_rate", "waste_percentage", "approved_quantity")
      for value in (-1, "NaN", "Infinity", "-Infinity")],
])
def test_patch_invalid_payload(client, db_session, payload):
    seed(db_session)
    create_link(client)
    assert client.patch(url() + "/MAT-1", json=payload).status_code == 422


def test_patch_not_found_and_ownership(client, db_session):
    seed(db_session)
    db_session.add(Project(project_id="PRJ-2", name="Other"))
    db_session.commit()
    for endpoint in (url("UNKNOWN") + "/MAT-1", url(work="UNKNOWN") + "/MAT-1",
                     url() + "/UNKNOWN", url() + "/MAT-1", url("PRJ-2") + "/MAT-1"):
        assert client.patch(endpoint, json={"status": "ACTIVE"}).status_code == 404


def test_patch_missing_price_and_work_quantity(client, db_session):
    _, work, _ = seed(db_session)
    create_link(client)
    response = client.patch(url() + "/MAT-1", json={"consumption_rate": 2})
    assert response.status_code == 200
    assert response.json()["material_total"] is None
    work.quantity = None
    db_session.commit()
    assert client.patch(url() + "/MAT-1", json={"consumption_rate": 3}).status_code == 422
    assert db_session.query(WorkMaterialLink).one().consumption_rate == 2


def test_patch_database_error_rolls_back(client, db_session, monkeypatch):
    seed(db_session)
    create_link(client)
    calls = []
    rollback = db_session.rollback
    def tracked_rollback():
        calls.append("rollback")
        rollback()
    monkeypatch.setattr(db_session, "rollback", tracked_rollback)
    monkeypatch.setattr(db_session, "commit", lambda: (_ for _ in ()).throw(
        OperationalError("UPDATE private SQL", {}, Exception("internal detail"))))
    response = client.patch(url() + "/MAT-1", json={"consumption_rate": 3})
    assert response.status_code == 500
    assert response.json() == {"detail": "Unable to update material link"}
    assert calls == ["rollback"]
    assert "private SQL" not in response.text
    assert "internal detail" not in response.text
    assert db_session.query(WorkMaterialLink).one().consumption_rate == 1


def test_empty_link_list(client, db_session):
    seed(db_session)
    response = client.get(url())
    assert response.status_code == 200
    assert response.json() == []


def test_unknown_project_work_and_material(client, db_session):
    seed(db_session)
    assert client.get(url("MISSING", "WRK-1")).status_code == 404
    assert client.get(url("PRJ-1", "MISSING")).status_code == 404
    assert create_link(client, material_id="MISSING").status_code == 404


def test_work_from_another_project_is_404(client, db_session):
    seed(db_session)
    other = Project(project_id="PRJ-2", name="Other")
    db_session.add(other)
    db_session.commit()
    assert client.get(url("PRJ-2", "WRK-1")).status_code == 404
    assert create_link(client, "PRJ-2", "WRK-1").status_code == 404


def test_minimal_create_hides_internal_ids_and_missing_price_total(client, db_session):
    seed(db_session)
    response = create_link(client)
    assert response.status_code == 201
    assert response.json() == {
        "material_id": "MAT-1",
        "name": "MAT-1",
        "specification": None,
        "normalized_unit": "кг",
        "unit_price": None,
        "consumption_rate": 1.0,
        "waste_percentage": 0.0,
        "calculated_quantity": 10.0,
        "approved_quantity": None,
        "effective_quantity": 10.0,
        "material_total": None,
        "status": "ACTIVE",
    }
    for field in ("id", "work_id"):
        assert field not in response.json()


def test_waste_formula_and_material_total(client, db_session):
    seed(db_session, price=5)
    response = create_link(client, consumption_rate=2, waste_percentage=10)
    assert response.status_code == 201
    assert response.json()["calculated_quantity"] == 22.0
    assert response.json()["effective_quantity"] == 22.0
    assert response.json()["material_total"] == 110.0


def test_approved_quantity_override(client, db_session):
    seed(db_session, price=2)
    response = create_link(client, approved_quantity=7.7777)
    assert response.status_code == 201
    assert response.json()["calculated_quantity"] == 10.0
    assert response.json()["effective_quantity"] == 7.778
    assert response.json()["material_total"] == 15.56


def test_quantity_and_money_round_half_up(client, db_session):
    seed(db_session, quantity=1.2345, price=2.005)
    response = create_link(client)
    assert response.status_code == 201
    assert response.json()["calculated_quantity"] == 1.235
    assert response.json()["effective_quantity"] == 1.235
    assert response.json()["material_total"] == 2.48


def test_get_uses_current_material_price_not_a_link_snapshot(client, db_session):
    _, _, material = seed(db_session, price=2)
    assert create_link(client).json()["material_total"] == 20.0

    material.unit_price = 3
    db_session.commit()

    response = client.get(url())
    assert response.status_code == 200
    assert response.json()[0]["unit_price"] == 3.0
    assert response.json()[0]["material_total"] == 30.0


def test_null_work_quantity_is_422(client, db_session):
    seed(db_session, quantity=None)
    assert create_link(client).status_code == 422


def test_zero_values_are_allowed(client, db_session):
    seed(db_session, quantity=0, price=0)
    response = create_link(client, consumption_rate=0, waste_percentage=0, approved_quantity=0)
    assert response.status_code == 201
    assert response.json()["calculated_quantity"] == 0.0
    assert response.json()["effective_quantity"] == 0.0
    assert response.json()["material_total"] == 0.0


@pytest.mark.parametrize("field", ["consumption_rate", "waste_percentage", "approved_quantity"])
@pytest.mark.parametrize("value", [-1, "NaN", "Infinity", "-Infinity"])
def test_invalid_numbers_are_422(client, db_session, field, value):
    seed(db_session)
    assert create_link(client, **{field: value}).status_code == 422


@pytest.mark.parametrize(
    "field",
    ["id", "work_id", "calculated_quantity", "effective_quantity", "material_total", "unknown"],
)
def test_forbidden_and_unknown_fields_are_422(client, db_session, field):
    seed(db_session)
    assert create_link(client, **{field: 1}).status_code == 422


def test_internal_integer_material_id_is_422(client, db_session):
    seed(db_session)
    assert create_link(client, material_id=1).status_code == 422


@pytest.mark.parametrize(
    "payload",
    [
        {"consumption_rate": 1},
        {"material_id": None, "consumption_rate": 1},
        {"material_id": "", "consumption_rate": 1},
        {"material_id": "   ", "consumption_rate": 1},
    ],
)
def test_missing_null_or_empty_material_id_is_422(client, db_session, payload):
    seed(db_session)
    assert client.post(url(), json=payload).status_code == 422


def test_missing_consumption_rate_is_422(client, db_session):
    seed(db_session)
    assert client.post(url(), json={"material_id": "MAT-1"}).status_code == 422


def test_duplicate_is_409_and_session_recovers(client, db_session):
    seed(db_session)
    assert create_link(client).status_code == 201
    assert create_link(client).status_code == 409
    second = Material(material_id="MAT-2", name="Second")
    db_session.add(second)
    db_session.commit()
    assert create_link(client, material_id="MAT-2").status_code == 201


def test_other_database_error_rolls_back_and_returns_generic_500(
    client, db_session, monkeypatch
):
    seed(db_session)
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
    response = create_link(client)
    assert response.status_code == 500
    assert response.json() == {"detail": "Unable to link material"}
    assert rollback_calls == 1
    assert "private SQL" not in response.text
    assert "database detail" not in response.text


def test_project_isolation_stable_order_and_get_calculations(client, db_session):
    _, work, first = seed(db_session, price=3)
    second = Material(material_id="MAT-2", name="Second", unit_price=4)
    db_session.add(second)
    db_session.commit()
    db_session.refresh(second)
    db_session.add_all([
        WorkMaterialLink(
            work_id=work.id,
            material_id=second.id,
            consumption_rate=2,
            waste_percentage=0,
        ),
        WorkMaterialLink(
            work_id=work.id,
            material_id=first.id,
            consumption_rate=1,
            waste_percentage=10,
        ),
    ])
    db_session.commit()
    response = client.get(url())
    assert response.status_code == 200
    assert [item["material_id"] for item in response.json()] == ["MAT-2", "MAT-1"]
    assert response.json()[0]["calculated_quantity"] == 20.0
    assert response.json()[0]["material_total"] == 80.0
    assert response.json()[1]["calculated_quantity"] == 11.0
    assert response.json()[1]["material_total"] == 33.0
