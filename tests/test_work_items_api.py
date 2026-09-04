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


PATCH_URL = "/api/v1/projects/PRJ-001/work-items/PRJ-001-WRK-001"


def test_patch_partial_trim_and_get(client, db_session):
    add_project(db_session)
    original = create_work(client, quantity=10, labor_unit_rate=2).json()
    r = client.patch(PATCH_URL, json={"name": "  Updated  "})
    assert r.status_code == 200
    assert r.json() == {**{k: v for k, v in original.items() if k != "id"}, "name": "Updated"}
    assert "id" not in r.json() and "project_id" not in r.json()
    assert client.get("/api/v1/projects/PRJ-001/work-items").json() == [{**original, "name": "Updated"}]
    r = client.patch(PATCH_URL, json={"unit": " m2 ", "wbs_code": " 1.2 ", "status": "VALID"})
    assert r.json()["unit"] == "м²"
    assert r.json()["wbs_code"] == "1.2"
    assert r.json()["status"] == "VALID"
    assert client.patch(PATCH_URL, json={"unit": " custom "}).json()["unit"] == "custom"
    r = client.patch(PATCH_URL, json={"unit": None, "wbs_code": None})
    assert r.json()["unit"] is None and r.json()["wbs_code"] is None


@pytest.mark.parametrize("payload,total", [
    ({"quantity": 10.005}, 20.01), ({"labor_unit_rate": 1.005}, 10.05),
    ({"quantity": 0}, 0), ({"labor_unit_rate": 0}, 0),
])
def test_patch_labor_rounding(client, db_session, payload, total):
    add_project(db_session)
    create_work(client, quantity=10, labor_unit_rate=2)
    r = client.patch(PATCH_URL, json=payload)
    assert r.status_code == 200
    assert r.json()["labor_total"] == total


@pytest.mark.parametrize("payload", [
    {}, *[{f: 1} for f in ("id", "work_id", "project_id", "labor_total", "unknown")],
    *[{"name": v} for v in (None, "", "  ")],
    *[{"status": v} for v in (None, "INVALID")],
    *[{f: v} for f in ("quantity", "labor_unit_rate")
      for v in (-1, "NaN", "Infinity", "-Infinity")],
    {"unit": " "}, {"wbs_code": " "},
])
def test_patch_validation(client, db_session, payload):
    add_project(db_session)
    original = create_work(client).json()
    assert client.patch(PATCH_URL, json=payload).status_code == 422
    assert client.get("/api/v1/projects/PRJ-001/work-items").json() == [original]


def test_patch_ownership(client, db_session):
    add_project(db_session)
    add_project(db_session, "OTHER")
    create_work(client)
    for url in (PATCH_URL.replace("projects/PRJ-001", "projects/MISSING"),
                PATCH_URL.replace("projects/PRJ-001", "projects/OTHER"),
                PATCH_URL + "-MISSING"):
        assert client.patch(url, json={"quantity": 3}).status_code == 404


@pytest.mark.parametrize("failure", ["query", "commit", "refresh"])
def test_patch_database_failure(client, db_session, monkeypatch, failure):
    add_project(db_session)
    create_work(client, quantity=10)
    events = []
    rollback = db_session.rollback
    def fail(*args, **kwargs):
        events.append("error")
        raise OperationalError("secret SQL", {}, Exception("internal detail"))
    def tracked_rollback():
        events.append("rollback")
        rollback()
    with monkeypatch.context() as patch:
        patch.setattr(db_session, failure, fail)
        patch.setattr(db_session, "rollback", tracked_rollback)
        r = client.patch(PATCH_URL, json={"quantity": 3})
    assert r.status_code == 500
    assert r.json() == {"detail": "Unable to update work item"}
    assert events == ["error", "rollback"]
    assert client.get("/api/v1/projects/PRJ-001/work-items").status_code == 200


def test_patch_recalculates_links_and_both_summaries_without_link_writes(client, db_session):
    from app.models.models import WorkMaterialLink
    add_project(db_session)
    assert create_work(client, quantity=10, labor_unit_rate=2).status_code == 201
    link_url = PATCH_URL + "/materials"
    for material_id, approved in (("M1", None), ("M2", 7), ("M3", 0)):
        assert client.post("/api/v1/materials", json={
            "material_id": material_id, "name": material_id, "unit_price": 3,
        }).status_code == 201
        assert client.post(link_url, json={
            "material_id": material_id, "consumption_rate": 2,
            "waste_percentage": 10, "approved_quantity": approved,
        }).status_code == 201
    before = [(l.id, l.calculated_quantity, l.approved_quantity)
              for l in db_session.query(WorkMaterialLink).order_by(WorkMaterialLink.id)]
    r = client.patch(PATCH_URL, json={"quantity": 20})
    assert r.status_code == 200 and r.json()["labor_total"] == 40
    links = client.get(link_url).json()
    assert [l["calculated_quantity"] for l in links] == [44, 44, 44]
    assert [l["effective_quantity"] for l in links] == [44, 7, 0]
    assert [l["material_total"] for l in links] == [132, 21, 0]
    for url in (PATCH_URL + "/summary", "/api/v1/projects/PRJ-001/budget-summary"):
        r = client.get(url)
        assert r.status_code == 200
        assert r.json()["material_subtotal_known"] == 153
        assert r.json()["subtotal_known_before_vat"] == 193
        assert r.json()["pricing_status"] == "COMPLETE"
    db_session.expire_all()
    after = [(l.id, l.calculated_quantity, l.approved_quantity)
             for l in db_session.query(WorkMaterialLink).order_by(WorkMaterialLink.id)]
    assert before == after


@pytest.mark.parametrize("payload", [
    {"quantity": None}, {"labor_unit_rate": None},
    {"quantity": None, "labor_unit_rate": None},
])
def test_nullable_create_and_patch(client, db_session, payload):
    add_project(db_session)
    created = create_work(client, **payload)
    assert created.status_code == 201 and created.json()["labor_total"] is None
    assert "id" in created.json()
    assert client.patch(PATCH_URL, json={"quantity": 3, "labor_unit_rate": 2}).json()["labor_total"] == 6
    r = client.patch(PATCH_URL, json=payload)
    assert r.status_code == 200 and r.json()["labor_total"] is None
    assert "id" not in r.json() and "project_id" not in r.json()


def test_patch_openapi_public_response(client):
    spec = client.get("/openapi.json").json()
    operation = spec["paths"]["/api/v1/projects/{project_id}/work-items/{work_id}"]["patch"]
    ref = operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].split("/")[-1]
    fields = spec["components"]["schemas"][ref]["properties"]
    assert set(fields) == {"work_id", "name", "wbs_code", "unit", "quantity", "labor_unit_rate", "labor_total", "status"}
    assert "id" in spec["components"]["schemas"]["ProjectWorkItemResponse"]["properties"]


def test_null_quantity_link_and_summary_runtime(client, db_session):
    from app.models.models import WorkMaterialLink
    add_project(db_session)
    create_work(client, quantity=10, labor_unit_rate=2)
    link_url = PATCH_URL + "/materials"
    for mid, approved, price in (("M1", None, 3), ("M2", 0, 3), ("M3", 7, 3), ("M4", 7, None)):
        assert client.post("/api/v1/materials", json={"material_id": mid, "name": mid, "unit_price": price}).status_code == 201
        assert client.post(link_url, json={"material_id": mid, "consumption_rate": 2, "approved_quantity": approved}).status_code == 201
    def persisted():
        return [(l.id, l.work_id, l.material_id, l.consumption_rate, l.waste_percentage,
                 l.calculated_quantity, l.approved_quantity, l.status)
                for l in db_session.query(WorkMaterialLink).order_by(WorkMaterialLink.id)]
    before = persisted()
    assert client.patch(PATCH_URL, json={"quantity": None}).status_code == 200
    response = client.get(link_url)
    assert response.status_code == 200
    links = response.json()
    assert [l["material_id"] for l in links] == ["M1", "M2", "M3", "M4"]
    assert [l["calculated_quantity"] for l in links] == [None] * 4
    assert [l["effective_quantity"] for l in links] == [None, 0, 7, 7]
    assert [l["material_total"] for l in links] == [None, 0, 21, None]
    for url in (PATCH_URL + "/summary", "/api/v1/projects/PRJ-001/budget-summary"):
        body = client.get(url).json()
        assert body["pricing_status"] == "INCOMPLETE"
        assert body["material_subtotal_known"] == 21
        assert body["subtotal_known_before_vat"] == 21
    project = client.get("/api/v1/projects/PRJ-001/budget-summary").json()
    assert project["missing_labor_work_ids"] == ["PRJ-001-WRK-001"]
    assert project["incomplete_work_count"] == 1
    # Restore quantity while clearing the rate: materials remain calculable.
    assert client.patch(PATCH_URL, json={"quantity": 20, "labor_unit_rate": None}).json()["labor_total"] is None
    assert client.get(link_url).json()[0]["calculated_quantity"] == 40
    assert client.get(PATCH_URL + "/summary").json()["pricing_status"] == "INCOMPLETE"
    assert client.patch(PATCH_URL, json={"labor_unit_rate": 2}).json()["labor_total"] == 40
    assert client.get(PATCH_URL + "/summary").json()["subtotal_known_before_vat"] == 181
    assert client.get("/api/v1/projects/PRJ-001/budget-summary").json()["subtotal_known_before_vat"] == 181
    assert client.patch(PATCH_URL, json={"quantity": 0}).json()["labor_total"] == 0
    assert client.get(link_url).json()[0]["calculated_quantity"] == 0
    db_session.expire_all()
    assert persisted() == before
