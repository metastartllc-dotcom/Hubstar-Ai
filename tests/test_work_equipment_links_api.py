import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Query, Session
from sqlalchemy.pool import StaticPool
from app.api.main import app
from app.core.database import Base, get_db
from app.models.models import Equipment, Project, StatusEnum, WorkEquipmentLink, WorkItem
from app.services.equipment_calculator import calculate_equipment_total, EquipmentCalculationError

BASE = "/api/v1/projects/P/work-items/W/equipment"


@pytest.fixture()
def context():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine); db = Session(engine)
    project = Project(project_id="P", name="Project"); db.add(project); db.flush()
    db.add_all([WorkItem(work_id="W", project_id=project.id, name="Work"),
                WorkItem(work_id="W2", project_id=project.id, name="Work 2"),
                Equipment(equipment_id="E", type="Crane", capacity="25 t", unit_rate=150000,
                          tariff_type="MNT/hour", operator_included=True, fuel_included=False,
                          delivery_included=True, included_delivery_one_way_distance_km=25),
                Equipment(equipment_id="E2", type="Loader", unit_rate=None, tariff_type=None)])
    db.commit()
    def override(): yield db
    app.dependency_overrides[get_db] = override
    try:
        with TestClient(app, raise_server_exceptions=False) as client: yield db, client, engine
    finally:
        app.dependency_overrides.pop(get_db, None); db.close(); Base.metadata.drop_all(engine); engine.dispose()


def test_empty_create_total_public_and_stable_order(context):
    db, client, _ = context
    assert client.get(BASE).json() == []
    first = client.post(BASE, json={"equipment_id":" E ", "usage_quantity":72})
    assert first.status_code == 201
    body = first.json(); assert body["equipment_id"] == "E" and body["equipment_total"] == 10800000
    assert body["operator_included"] is True and body["fuel_included"] is False
    assert body["included_delivery_one_way_distance_km"] == 25
    assert not ({"id", "work_item_id"} & body.keys())
    second = client.post(BASE, json={"equipment_id":"E2", "usage_quantity":0})
    assert second.status_code == 201 and second.json()["equipment_total"] is None
    assert [x["equipment_id"] for x in client.get(BASE).json()] == ["E", "E2"]
    assert db.query(WorkEquipmentLink).count() == 2


def test_snapshot_is_immutable_until_explicit_link_patch(context):
    db, client, _ = context
    original = client.post(BASE, json={"equipment_id":"E", "usage_quantity":72}).json()
    changed = client.patch("/api/v1/equipment/E", json={"unit_rate":200000, "tariff_type":"MNT/day",
        "operator_included":False, "fuel_included":True, "delivery_included":False,
        "included_delivery_one_way_distance_km":None})
    assert changed.status_code == 200
    assert client.get(BASE).json()[0] == original
    patched = client.patch(BASE + "/E", json={"agreed_unit_rate":200000, "tariff_type":"MNT/day",
        "operator_included":False, "fuel_included":True, "delivery_included":False,
        "included_delivery_one_way_distance_km":None})
    assert patched.status_code == 200 and patched.json()["equipment_total"] == 14400000
    assert patched.json()["delivery_included"] is False
    work2 = "/api/v1/projects/P/work-items/W2/equipment"
    fresh = client.post(work2, json={"equipment_id":"E", "usage_quantity":1})
    assert fresh.json()["agreed_unit_rate"] == 200000 and fresh.json()["tariff_type"] == "MNT/day"


@pytest.mark.parametrize("master_status", [StatusEnum.REJECTED, StatusEnum.SUPERSEDED])
def test_ineligible_master_status_is_conflict(context, master_status):
    db, client, _ = context
    equipment = db.query(Equipment).filter_by(equipment_id="E").one(); equipment.status = master_status; db.commit()
    response = client.post(BASE, json={"equipment_id":"E", "usage_quantity":1})
    assert response.status_code == 409
    assert response.json() == {"detail":"Equipment is not eligible for linking"}
    assert db.query(WorkEquipmentLink).count() == 0 and not db.dirty


@pytest.mark.parametrize("master_status", [StatusEnum.NEEDS_REVIEW, StatusEnum.ACTIVE_WITH_WARNINGS])
def test_master_warning_status_cannot_be_downgraded(context, master_status):
    db, client, _ = context
    equipment = db.query(Equipment).filter_by(equipment_id="E").one(); equipment.status = master_status; db.commit()
    response = client.post(BASE, json={"equipment_id":"E", "usage_quantity":1, "status":"ACTIVE"})
    assert response.status_code == 201 and response.json()["status"] == master_status.value


@pytest.mark.parametrize("changes", [
    {"unit_rate": 1, "tariff_type": None},
    {"unit_rate": -1}, {"unit_rate": float("inf")},
    {"delivery_included": False, "included_delivery_one_way_distance_km": 1},
    {"delivery_included": True, "included_delivery_one_way_distance_km": -1},
])
def test_invalid_persisted_master_is_conflict(context, changes):
    db, client, _ = context
    equipment = db.query(Equipment).filter_by(equipment_id="E").one()
    for field, value in changes.items(): setattr(equipment, field, value)
    db.commit()
    response = client.post(BASE, json={"equipment_id":"E", "usage_quantity":1})
    assert response.status_code == 409 and response.json() == {"detail":"Equipment is not eligible for linking"}
    assert db.query(WorkEquipmentLink).count() == 0 and not db.dirty


@pytest.mark.parametrize("value", [-1, "2", True, "NaN", "Infinity"])
def test_strict_usage_validation(context, value):
    _, client, _ = context
    assert client.post(BASE, json={"equipment_id":"E", "usage_quantity":value}).status_code == 422


def test_duplicate_not_found_ownership_and_patch_contract(context):
    db, client, _ = context
    assert client.get("/api/v1/projects/X/work-items/W/equipment").status_code == 404
    assert client.get("/api/v1/projects/P/work-items/X/equipment").status_code == 404
    assert client.post(BASE, json={"equipment_id":"X", "usage_quantity":1}).status_code == 404
    assert client.post(BASE, json={"equipment_id":"E", "usage_quantity":1}).status_code == 201
    assert client.post(BASE, json={"equipment_id":" E ", "usage_quantity":2}).status_code == 409
    assert client.patch(BASE + "/X", json={"usage_quantity":2}).status_code == 404
    for payload in ({}, {"id":1}, {"equipment_id":"X"}, {"usage_quantity":None}):
        assert client.patch(BASE + "/E", json=payload).status_code == 422
    assert client.patch(BASE + "/E", json={"usage_quantity":0}).json()["equipment_total"] == 0
    assert db.query(WorkEquipmentLink).one().agreed_unit_rate == 150000


def test_unique_constraint_race_fallback_and_session_recovery(context, monkeypatch):
    db, client, _ = context
    work = db.query(WorkItem).filter_by(work_id="W").one(); equipment = db.query(Equipment).filter_by(equipment_id="E").one()
    db.add(WorkEquipmentLink(work_item_id=work.id, equipment_id=equipment.id, usage_quantity=1,
                             agreed_unit_rate=150000, tariff_type_snapshot="MNT/hour")); db.commit()
    original = Query.first; bypassed = False
    def first(query):
        nonlocal bypassed
        entity = query.column_descriptions[0].get("entity")
        if entity is WorkEquipmentLink and not bypassed:
            bypassed = True; return None
        return original(query)
    monkeypatch.setattr(Query, "first", first)
    response = client.post(BASE, json={"equipment_id":"E", "usage_quantity":2})
    assert response.status_code == 409 and db.query(WorkEquipmentLink).count() == 1
    assert client.get(BASE).status_code == 200


@pytest.mark.parametrize("payload", [
    {"agreed_unit_rate": 10, "tariff_type": None},
    {"tariff_type": " "},
    {"delivery_included": False, "included_delivery_one_way_distance_km": 1},
    {"delivery_included": None, "included_delivery_one_way_distance_km": 1},
    {"operator_included": 1}, {"fuel_included":"true"},
    {"included_delivery_one_way_distance_km":"1"},
])
def test_patch_cross_and_strict_validation_leaves_row_clean(context, payload):
    db, client, _ = context
    client.post(BASE, json={"equipment_id":"E", "usage_quantity":1})
    before = tuple(db.execute(text("select usage_quantity,agreed_unit_rate,tariff_type_snapshot,delivery_included_snapshot,included_delivery_one_way_distance_km_snapshot from work_equipment_links")).one())
    assert client.patch(BASE + "/E", json=payload).status_code == 422
    assert tuple(db.execute(text("select usage_quantity,agreed_unit_rate,tariff_type_snapshot,delivery_included_snapshot,included_delivery_one_way_distance_km_snapshot from work_equipment_links")).one()) == before
    assert not db.dirty and not db.new and not db.deleted
    db.commit()
    assert client.patch(BASE + "/E", json={"usage_quantity":2}).status_code == 200


def test_calculator_rounding_and_guards():
    assert calculate_equipment_total(1, 2.345) == Decimal("2.35")
    assert calculate_equipment_total(0, 1) == Decimal("0.00")
    assert calculate_equipment_total(1, 0) == Decimal("0.00")
    assert calculate_equipment_total(1, None) is None
    for value in (-1, float("nan"), float("inf")):
        with pytest.raises(EquipmentCalculationError): calculate_equipment_total(value, 1)


def test_openapi_has_no_internal_ids(context):
    _, client, _ = context
    schema = client.get("/openapi.json").json()["components"]["schemas"]
    public = schema["WorkEquipmentPublicResponse"]["properties"]
    assert not ({"id", "work_item_id"} & public.keys())
    assert set(schema["WorkEquipmentCreateRequest"]["required"]) >= {"equipment_id", "usage_quantity"}


def test_list_is_bounded_query_count(context):
    _, client, engine = context
    client.post(BASE, json={"equipment_id":"E", "usage_quantity":1})
    count = 0
    def before(*_):
        nonlocal count; count += 1
    event.listen(engine, "before_cursor_execute", before)
    try: assert client.get(BASE).status_code == 200
    finally: event.remove(engine, "before_cursor_execute", before)
    assert count == 3  # project, owned work, joined links/equipment


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_json_numbers_are_rejected(context, literal):
    _, client, _ = context
    response = client.post(BASE, content='{"equipment_id":"E","usage_quantity":' + literal + '}',
                           headers={"content-type":"application/json"})
    assert response.status_code == 422


def test_database_error_is_sanitized_and_rolls_back(context):
    db, client, _ = context
    db.execute(text("drop table work_equipment_links")); db.commit()
    response = client.get(BASE)
    assert response.status_code == 500
    assert response.json() == {"detail": "Unable to persist work equipment"}
    assert "sql" not in response.text.lower() and not db.in_transaction()
