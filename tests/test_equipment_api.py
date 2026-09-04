import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.api.main import app
from app.core.database import Base, get_db
from app.models.models import Equipment
from app.repositories import equipment as repository

URL = "/api/v1/equipment"
FLAGS = ("operator_included", "fuel_included", "delivery_included")
STRINGS = ("master_id", "model", "capacity", "location", "tariff_type", "availability")


@pytest.fixture()
def context():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = Session(engine)
    def override():
        yield db
    app.dependency_overrides[get_db] = override
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield db, client
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def post(client, **values):
    return client.post(URL, json={"equipment_id": "E", "type": "Crane", **values})


@pytest.mark.parametrize("value", ["omitted", None, False, True])
def test_orm_nullable_flags(context, value):
    db, _ = context
    fields = {} if value == "omitted" else dict.fromkeys(FLAGS, value)
    db.add(Equipment(**fields))
    db.commit()
    expected = None if value == "omitted" else value
    assert tuple(db.execute(text("SELECT operator_included, fuel_included, delivery_included FROM equipments")).one()) == (expected,) * 3
    columns = {c["name"]: c for c in inspect(db.bind).get_columns("equipments")}
    for flag in FLAGS:
        assert columns[flag]["nullable"] and columns[flag]["default"] is None
        assert Equipment.__table__.c[flag].default is None


@pytest.mark.parametrize("value", ["omitted", None, False, True])
def test_api_nullable_flags(context, value):
    db, client = context
    fields = {} if value == "omitted" else dict.fromkeys(FLAGS, value)
    r = post(client, **fields)
    assert r.status_code == 201
    expected = None if value == "omitted" else value
    for flag in FLAGS:
        assert r.json()[flag] is expected
        assert getattr(db.query(Equipment).one(), flag) is expected
    assert r.json()["status"] == "ACTIVE"
    assert "id" not in r.json()


def test_runtime_list_detail_full_pagination(context):
    _, client = context
    assert client.get(URL).json() == []
    assert client.get(URL + "/missing").status_code == 404
    minimal = post(client).json()
    full = post(client, equipment_id="  Z  ", type="  Loader  ", unit_rate=0,
                **{s: " text " for s in STRINGS}, **dict.fromkeys(FLAGS, True))
    assert full.status_code == 201
    assert full.json()["equipment_id"] == "Z" and full.json()["type"] == "Loader"
    assert all(full.json()[s] == "text" for s in STRINGS)
    assert client.get(URL + "/Z").json() == full.json()
    assert client.get(URL).json() == [minimal, full.json()]
    assert client.get(URL + "?offset=1&limit=1").json() == [full.json()]
    assert client.get(URL + "?offset=2&limit=100").json() == []
    for query in ("offset=-1", "limit=0", "limit=101"):
        assert client.get(URL + "?" + query).status_code == 422


@pytest.mark.parametrize("field", ["equipment_id", "type"])
@pytest.mark.parametrize("value", [None, "", " ", "missing"])
def test_required(context, field, value):
    _, client = context
    payload = {"equipment_id": "E", "type": "Crane"}
    if value == "missing":
        del payload[field]
    else:
        payload[field] = value
    assert client.post(URL, json=payload).status_code == 422


@pytest.mark.parametrize("field", STRINGS)
def test_optional_strings(context, field):
    _, client = context
    assert post(client, **{field: " "}).status_code == 422
    assert post(client, **{field: None}).status_code == 201


@pytest.mark.parametrize("field", FLAGS)
@pytest.mark.parametrize("value", ["true", "false", 0, 1])
def test_strict_flags(context, field, value):
    assert post(context[1], **{field: value}).status_code == 422


@pytest.mark.parametrize("value", [-1, "NaN", "Infinity", "-Infinity"])
def test_rate_invalid(context, value):
    assert post(context[1], unit_rate=value, tariff_type="hour").status_code == 422


def test_rate_tariff_contract(context):
    _, client = context
    for rate in (0, 100):
        assert post(client, unit_rate=rate).status_code == 422
    assert post(client, unit_rate=None, tariff_type="hour").status_code == 201


@pytest.mark.parametrize("value", [None, "INVALID"])
def test_status(context, value):
    assert post(context[1], status=value).status_code == 422


@pytest.mark.parametrize("field", ["id", "project_id", "work_id", "supplier_id", "total", "total_cost", "usage_quantity", "unknown"])
def test_forbidden(context, field):
    assert post(context[1], **{field: 1}).status_code == 422


def test_openapi(context):
    spec = context[1].get("/openapi.json").json()
    expected = {"equipment_id", "type", "unit_rate", "status", *FLAGS, *STRINGS}
    for name in ("EquipmentCreateRequest", "EquipmentPublicResponse"):
        assert set(spec["components"]["schemas"][name]["properties"]) == expected


def test_duplicate_and_recovery(context):
    _, client = context
    assert post(client).status_code == 201
    for identifier in ("E", " E "):
        assert post(client, equipment_id=identifier).status_code == 409
    assert post(client, equipment_id="AFTER").status_code == 201


@pytest.mark.parametrize("duplicate", [True, False])
def test_integrity_rollback_before_lookup(context, monkeypatch, duplicate):
    db, client = context
    events = []
    results = iter([None, Equipment(equipment_id="E") if duplicate else None])
    rollback = db.rollback
    def find(*args):
        events.append("lookup")
        return next(results)
    def fail():
        events.append("commit")
        raise IntegrityError("SECRET SQL", {}, Exception("internal"))
    def roll():
        events.append("rollback")
        rollback()
    with monkeypatch.context() as m:
        m.setattr(repository, "_find", find)
        m.setattr(db, "commit", fail)
        m.setattr(db, "rollback", roll)
        r = post(client)
    assert r.status_code == (409 if duplicate else 500)
    assert events == ["lookup", "commit", "rollback", "lookup"]
    assert "SECRET" not in r.text and "internal" not in r.text
    assert post(client, equipment_id="AFTER").status_code == 201


@pytest.mark.parametrize("method", ["query", "commit", "refresh"])
def test_database_error(context, monkeypatch, method):
    db, client = context
    events = []
    rollback = db.rollback
    def fail(*args, **kwargs):
        raise OperationalError("SECRET SQL", {}, Exception("internal"))
    def roll():
        events.append("rollback")
        rollback()
    with monkeypatch.context() as m:
        m.setattr(db, method, fail)
        m.setattr(db, "rollback", roll)
        r = post(client)
    assert r.status_code == 500 and r.json() == {"detail": "Unable to create equipment"}
    assert events == ["rollback"]
    assert post(client, equipment_id="AFTER").status_code == 201


def test_equipment_does_not_change_summaries(context):
    _, client = context
    assert client.post("/api/v1/projects", json={"project_id": "P", "name": "Project"}).status_code == 201
    assert client.post("/api/v1/projects/P/work-items", json={"work_id": "W", "name": "Work", "quantity": 10, "labor_unit_rate": 2}).status_code == 201
    urls = ["/api/v1/projects/P/work-items/W/summary", "/api/v1/projects/P/budget-summary"]
    before = [client.get(u).json() for u in urls]
    assert post(client, unit_rate=100, tariff_type="hour").status_code == 201
    assert [client.get(u).json() for u in urls] == before
    assert client.patch(URL + "/E", json={"unit_rate": 200}).status_code == 200
    assert [client.get(u).json() for u in urls] == before


def test_patch_runtime_partial_and_cross_field(context):
    db, client = context
    original = post(client).json()
    r = client.patch(URL + "/E", json={"type": " Loader ", "unit_rate": 10, "tariff_type": " hour "})
    assert r.status_code == 200
    assert r.json() == {**original, "type": "Loader", "unit_rate": 10, "tariff_type": "hour"}
    for flag in FLAGS:
        for value in (None, False, True):
            r = client.patch(URL + "/E", json={flag: value})
            assert r.status_code == 200 and r.json()[flag] is value
            db.expire_all()
            assert getattr(db.query(Equipment).one(), flag) is value
    assert client.patch(URL + "/E", json={"unit_rate": 0}).json()["unit_rate"] == 0
    before = client.get(URL + "/E").json()
    assert client.patch(URL + "/E", json={"type": "Must not persist", "tariff_type": None}).status_code == 422
    assert client.get(URL + "/E").json() == before
    assert client.patch(URL + "/E", json={"tariff_type": "day"}).json()["unit_rate"] == 0
    assert client.patch(URL + "/E", json={"tariff_type": None, "unit_rate": None}).status_code == 200
    before = client.get(URL + "/E").json()
    assert client.patch(URL + "/E", json={"unit_rate": 0}).status_code == 422
    assert client.get(URL + "/E").json() == before
    assert client.patch(URL + "/E", json={"tariff_type": "hour"}).status_code == 200
    assert client.patch(URL + "/E", json={"unit_rate": 25}).json()["unit_rate"] == 25
    assert client.patch(URL + "/E", json={"unit_rate": None}).json()["unit_rate"] is None
    assert client.patch(URL + "/MISSING", json={"type": "X"}).status_code == 404


@pytest.mark.parametrize("field", STRINGS)
def test_patch_optional_strings(context, field):
    _, client = context
    post(client)
    r = client.patch(URL + "/E", json={field: " text "})
    assert r.status_code == 200 and r.json()[field] == "text"
    assert client.patch(URL + "/E", json={field: " "}).status_code == 422
    assert client.patch(URL + "/E", json={field: None}).json()[field] is None


@pytest.mark.parametrize("payload", [
    {}, *[{"type": v} for v in (None, "", " ")],
    *[{"status": v} for v in (None, "INVALID")],
    *[{f: 1} for f in ("id", "equipment_id", "project_id", "work_id", "supplier_id", "usage_quantity", "total", "total_cost", "unknown")],
    *[{"unit_rate": v} for v in (-1, "NaN", "Infinity", "-Infinity")],
    *[{f: v} for f in FLAGS for v in ("true", "false", 1, 0)],
])
def test_patch_invalid(context, payload):
    _, client = context
    before = post(client).json()
    assert client.patch(URL + "/E", json=payload).status_code == 422
    assert client.get(URL + "/E").json() == before


@pytest.mark.parametrize("method", ["query", "commit", "refresh"])
def test_patch_database_errors(context, monkeypatch, method):
    db, client = context
    post(client)
    calls = []
    rollback = db.rollback
    def fail(*args, **kwargs):
        raise OperationalError("SECRET SQL", {}, Exception("internal"))
    def roll():
        calls.append("rollback")
        rollback()
    with monkeypatch.context() as m:
        m.setattr(db, method, fail)
        m.setattr(db, "rollback", roll)
        r = client.patch(URL + "/E", json={"type": "Updated"})
    assert r.status_code == 500 and r.json() == {"detail": "Unable to update equipment"}
    assert calls == ["rollback"]
    assert client.patch(URL + "/E", json={"status": "VALID"}).status_code == 200


def test_patch_openapi(context):
    spec = context[1].get("/openapi.json").json()
    operation = spec["paths"][URL + "/{equipment_id}"]["patch"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("/EquipmentPublicResponse")
    fields = spec["components"]["schemas"]["EquipmentUpdateRequest"]["properties"]
    assert set(fields) == {"type", "unit_rate", "status", *FLAGS, *STRINGS}


def test_invalid_patch_leaves_no_dirty_state_or_autoflush(context):
    from sqlalchemy import event
    db, client = context
    before = post(client, unit_rate=10, tariff_type="hour").json()
    flushed = []
    def on_flush(*args):
        flushed.append(True)
    event.listen(db, "before_flush", on_flush)
    try:
        r = client.patch(URL + "/E", json={"type": "Invalid change", "tariff_type": None})
        assert r.status_code == 422
        assert not db.dirty and not db.new and not db.deleted
        stored = db.query(Equipment).filter_by(equipment_id="E").one()
        assert stored.type == before["type"] and stored.tariff_type == "hour"
        db.commit()
        assert not flushed
        assert client.get(URL + "/E").json() == before
    finally:
        event.remove(db, "before_flush", on_flush)
    assert client.patch(URL + "/E", json={"type": "Valid change"}).status_code == 200
    assert client.get(URL + "/E").json()["type"] == "Valid change"
    assert not db.dirty and not db.new and not db.deleted
