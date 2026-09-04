import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.exc import OperationalError
from app.api.main import app
from app.core.database import Base, get_db
from app.models.models import Project, WorkItem, Material, WorkMaterialLink

URL = "/api/v1/projects/P/budget-summary"


@pytest.fixture()
def context():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, autoflush=False)()
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


def project(db, external="P"):
    p = Project(project_id=external, name=external)
    db.add(p)
    db.commit()
    return p


def work(db, p, external="W", labor=100, status="ACTIVE"):
    w = WorkItem(project_id=p.id, work_id=external, name=external, quantity=10, labor_total=labor, status=status)
    db.add(w)
    db.commit()
    return w


def material(db, external="M", price=2, status="ACTIVE"):
    m = Material(material_id=external, name=external, unit_price=price, status=status)
    db.add(m)
    db.commit()
    return m


def link(db, w, m, quantity=10, approved=None, status="ACTIVE"):
    db.add(WorkMaterialLink(work_id=w.id, material_id=m.id, calculated_quantity=quantity,
                           consumption_rate=1, waste_percentage=0,
                           approved_quantity=approved, status=status))
    db.commit()


def test_unknown_and_empty(context):
    db, client = context
    assert client.get(URL).status_code == 404
    project(db)
    r = client.get(URL)
    assert r.status_code == 200
    assert r.json()["pricing_status"] == "NO_WORK_ITEMS"
    assert r.json()["works"] == []
    assert r.json()["subtotal_known_before_vat"] == 0


@pytest.mark.parametrize("count", [1, 3])
def test_complete_shared_material_and_bounded_queries(context, count):
    db, client = context
    p = project(db)
    m = material(db)
    for i in range(count):
        link(db, work(db, p, f"W-{i}"), m)
    other = project(db, "OTHER")
    link(db, work(db, other, "OTHER-W", labor=999), m)
    statements = []
    def capture(conn, cursor, statement, *args):
        statements.append(statement)
    event.listen(db.bind, "before_cursor_execute", capture)
    try:
        r = client.get(URL)
    finally:
        event.remove(db.bind, "before_cursor_execute", capture)
    assert r.status_code == 200
    b = r.json()
    assert len(statements) == 3
    assert all(s.lstrip().upper().startswith("SELECT") for s in statements)
    assert b["pricing_status"] == "COMPLETE"
    assert b["complete_work_count"] == count
    assert b["material_link_count"] == count
    assert b["labor_subtotal_known"] == count * 100
    assert b["material_subtotal_known"] == count * 20
    assert b["subtotal_known_before_vat"] == count * 120
    assert [w["work_id"] for w in b["works"]] == [f"W-{i}" for i in range(count)]
    assert "id" not in b and all("id" not in w for w in b["works"])
    assert "quantity" not in b


@pytest.mark.parametrize("labor,price,review,expected", [
    (None, 2, False, "INCOMPLETE"),
    (100, None, False, "INCOMPLETE"),
    (100, 2, True, "NEEDS_REVIEW"),
    (100, None, True, "INCOMPLETE"),
    (100, 0, False, "COMPLETE"),
])
def test_pricing_states(context, labor, price, review, expected):
    db, client = context
    w = work(db, project(db), labor=labor)
    m = material(db, price=price)
    link(db, w, m, status="NEEDS_REVIEW" if review else "ACTIVE")
    b = client.get(URL).json()
    assert b["pricing_status"] == expected
    assert b["missing_labor_work_ids"] == (["W"] if labor is None else [])
    assert b["missing_labor_work_count"] == int(labor is None)
    assert b["priced_material_link_count"] == int(price is not None)
    assert b["has_review_warnings"] == review


def test_pair_order_and_occurrences(context):
    db, client = context
    p = project(db)
    w2, w1 = work(db, p, "W2"), work(db, p, "W1")
    m2, m1 = material(db, "M2", None), material(db, "M1", None)
    for w in (w2, w1):
        for m in (m2, m1):
            link(db, w, m, status="NEEDS_REVIEW")
    b = client.get(URL).json()
    pairs = [{"work_id": w, "material_id": m} for w in ("W2", "W1") for m in ("M2", "M1")]
    assert b["missing_price_links"] == pairs
    assert b["needs_review_links"] == pairs
    assert b["missing_price_link_count"] == 4
    assert b["needs_review_link_count"] == 4


def test_approved_rounding_dynamic_price(context):
    db, client = context
    w = work(db, project(db), labor=1.005)
    m = material(db, price=2)
    link(db, w, m, approved=7.7777)
    b = client.get(URL).json()
    assert b["labor_subtotal_known"] == 1.01
    assert b["material_subtotal_known"] == 15.56
    assert b["subtotal_known_before_vat"] == 16.57
    assert client.patch("/api/v1/materials/M", json={"unit_price": 3}).status_code == 200
    assert client.get(URL).json()["material_subtotal_known"] == 23.33


def test_work_review_and_missing_labor_without_links(context):
    db, client = context
    w = work(db, project(db), status="NEEDS_REVIEW")
    assert client.get(URL).json()["pricing_status"] == "INCOMPLETE"
    w.labor_total = None
    db.commit()
    b = client.get(URL).json()
    assert b["pricing_status"] == "INCOMPLETE"
    assert b["works"][0]["labor_total"] is None


def assert_count_partition(body):
    assert sum(body[k] for k in ("complete_work_count", "incomplete_work_count", "needs_review_work_count")) == body["work_item_count"]
    assert body["no_materials_work_count"] <= body["incomplete_work_count"]


def test_no_material_work_is_incomplete(context):
    db, client = context
    p = project(db)
    empty = client.get(URL).json()
    assert empty["pricing_status"] == "NO_WORK_ITEMS"
    assert_count_partition(empty)
    work(db, p)
    b = client.get(URL).json()
    assert b["pricing_status"] == "INCOMPLETE"
    assert b["is_pricing_complete"] is False
    assert b["no_materials_work_count"] == 1
    assert b["no_materials_work_ids"] == ["W"]
    assert b["incomplete_work_count"] == 1
    assert b["works"][0]["pricing_status"] == "INCOMPLETE"
    assert "id" not in b and "id" not in b["works"][0]
    assert_count_partition(b)


def test_mixed_states_no_material_order(context):
    db, client = context
    p = project(db)
    work(db, p, "EMPTY-Z")
    priced = material(db)
    link(db, work(db, p, "COMPLETE"), priced)
    link(db, work(db, p, "REVIEW"), priced, status="NEEDS_REVIEW")
    link(db, work(db, p, "MISSING", labor=None), priced)
    work(db, p, "EMPTY-A")
    b = client.get(URL).json()
    assert b["pricing_status"] == "INCOMPLETE"
    assert b["work_item_count"] == 5
    assert b["complete_work_count"] == 1
    assert b["needs_review_work_count"] == 1
    assert b["incomplete_work_count"] == 3
    assert b["no_materials_work_count"] == 2
    assert b["no_materials_work_ids"] == ["EMPTY-Z", "EMPTY-A"]
    assert_count_partition(b)


def test_db_error_generic(context, monkeypatch):
    db, client = context
    monkeypatch.setattr(db, "query", lambda *args: (_ for _ in ()).throw(
        OperationalError("SELECT private SQL", {}, Exception("internal detail"))))
    r = client.get(URL)
    assert r.status_code == 500
    assert r.json() == {"detail": "Unable to read project budget"}
    assert "private SQL" not in r.text and "internal detail" not in r.text
