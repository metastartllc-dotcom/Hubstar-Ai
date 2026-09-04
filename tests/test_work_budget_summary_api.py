import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.main import app
from app.core.database import Base, get_db
from app.models.models import Material, Project, StatusEnum, WorkItem, WorkMaterialLink


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = factory()
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


def summary_url(project_id="PRJ-1", work_id="WRK-1"):
    return f"/api/v1/projects/{project_id}/work-items/{work_id}/summary"


def seed_work(db, *, project_id="PRJ-1", work_id="WRK-1", labor_total=100):
    project = Project(project_id=project_id, name="Project")
    db.add(project)
    db.commit()
    db.refresh(project)
    work = WorkItem(
        project_id=project.id,
        work_id=work_id,
        name="Work",
        unit="м²",
        quantity=10,
        labor_unit_rate=10 if labor_total is not None else None,
        labor_total=labor_total,
    )
    db.add(work)
    db.commit()
    db.refresh(work)
    return project, work


def add_link(
    db,
    work,
    material_id,
    *,
    price=2,
    calculated=10,
    approved=None,
    unit="кг",
    link_status=StatusEnum.ACTIVE,
    material_status=StatusEnum.ACTIVE,
):
    material = Material(
        material_id=material_id,
        name=material_id,
        normalized_unit=unit,
        unit_price=price,
        status=material_status,
    )
    db.add(material)
    db.commit()
    db.refresh(material)
    link = WorkMaterialLink(
        work_id=work.id,
        material_id=material.id,
        consumption_rate=calculated / work.quantity,
        waste_percentage=0,
        calculated_quantity=calculated,
        approved_quantity=approved,
        status=link_status,
    )
    db.add(link)
    db.commit()
    return material


def test_unknown_project_work_and_cross_project_are_404(client, db_session):
    seed_work(db_session)
    seed_work(db_session, project_id="PRJ-2", work_id="WRK-2")
    assert client.get(summary_url("UNKNOWN", "WRK-1")).status_code == 404
    assert client.get(summary_url("PRJ-1", "UNKNOWN")).status_code == 404
    assert client.get(summary_url("PRJ-2", "WRK-1")).status_code == 404


def test_no_materials_is_no_materials(client, db_session):
    seed_work(db_session)
    response = client.get(summary_url())
    assert response.status_code == 200
    assert response.json()["pricing_status"] == "NO_MATERIALS"
    assert response.json()["material_link_count"] == 0
    assert response.json()["material_subtotal_known"] == 0.0
    assert response.json()["subtotal_known_before_vat"] == 100.0


def test_complete_known_subtotals_and_internal_ids_hidden(client, db_session):
    _, work = seed_work(db_session, labor_total=100)
    add_link(db_session, work, "MAT-1", price=2, calculated=10)
    add_link(db_session, work, "MAT-2", price=3, calculated=5, unit="л")
    response = client.get(summary_url())
    assert response.status_code == 200
    body = response.json()
    assert body["pricing_status"] == "COMPLETE"
    assert body["priced_material_count"] == 2
    assert body["material_subtotal_known"] == 35.0
    assert body["subtotal_known_before_vat"] == 135.0
    assert body["is_pricing_complete"] is True
    assert not any(key in body for key in ("id", "project_internal_id", "work_internal_id"))
    assert "material_quantity_total" not in body


def test_missing_material_price_is_incomplete(client, db_session):
    _, work = seed_work(db_session)
    add_link(db_session, work, "MAT-1", price=None)
    body = client.get(summary_url()).json()
    assert body["pricing_status"] == "INCOMPLETE"
    assert body["priced_material_count"] == 0
    assert body["missing_price_count"] == 1
    assert body["missing_price_material_ids"] == ["MAT-1"]


def test_missing_labor_is_incomplete_and_not_added_as_zero(client, db_session):
    _, work = seed_work(db_session, labor_total=None)
    add_link(db_session, work, "MAT-1", price=2)
    body = client.get(summary_url()).json()
    assert body["pricing_status"] == "INCOMPLETE"
    assert body["material_subtotal_known"] == 20.0
    assert body["subtotal_known_before_vat"] == 20.0
    assert "Labor total is unavailable" in body["warnings"]


def test_incomplete_has_priority_over_review_and_order_is_stable(client, db_session):
    _, work = seed_work(db_session)
    add_link(
        db_session,
        work,
        "MAT-2",
        price=None,
        link_status=StatusEnum.NEEDS_REVIEW,
    )
    add_link(
        db_session,
        work,
        "MAT-1",
        price=None,
        material_status=StatusEnum.NEEDS_REVIEW,
    )
    body = client.get(summary_url()).json()
    assert body["pricing_status"] == "INCOMPLETE"
    assert body["has_review_warnings"] is True
    assert body["missing_price_material_ids"] == ["MAT-2", "MAT-1"]
    assert body["needs_review_material_ids"] == ["MAT-2", "MAT-1"]


def test_fully_priced_review_is_needs_review(client, db_session):
    _, work = seed_work(db_session)
    add_link(
        db_session,
        work,
        "MAT-1",
        price=2,
        link_status=StatusEnum.NEEDS_REVIEW,
    )
    body = client.get(summary_url()).json()
    assert body["pricing_status"] == "NEEDS_REVIEW"
    assert body["is_pricing_complete"] is True
    assert body["needs_review_count"] == 1


def test_link_and_material_review_status_count_once(client, db_session):
    _, work = seed_work(db_session)
    add_link(
        db_session,
        work,
        "MAT-1",
        price=2,
        link_status=StatusEnum.NEEDS_REVIEW,
        material_status=StatusEnum.NEEDS_REVIEW,
    )
    body = client.get(summary_url()).json()
    assert body["needs_review_count"] == 1
    assert body["needs_review_material_ids"] == ["MAT-1"]
    assert body["warnings"].count("Material needs review: MAT-1") == 1


def test_money_uses_two_place_round_half_up(client, db_session):
    _, work = seed_work(db_session, labor_total=0)
    add_link(db_session, work, "MAT-1", price=2.005, calculated=1.235)
    body = client.get(summary_url()).json()
    assert body["material_subtotal_known"] == 2.48
    assert body["subtotal_known_before_vat"] == 2.48


def test_zero_price_is_priced_and_approved_quantity_is_used(client, db_session):
    _, work = seed_work(db_session)
    add_link(db_session, work, "MAT-ZERO", price=0, calculated=10)
    add_link(db_session, work, "MAT-APPROVED", price=2, calculated=10, approved=7)
    body = client.get(summary_url()).json()
    assert body["priced_material_count"] == 2
    assert body["missing_price_count"] == 0
    assert body["material_subtotal_known"] == 14.0
    assert body["subtotal_known_before_vat"] == 114.0


def test_current_material_price_dynamically_changes_summary(client, db_session):
    _, work = seed_work(db_session)
    material = add_link(db_session, work, "MAT-1", price=2, calculated=10)
    assert client.get(summary_url()).json()["material_subtotal_known"] == 20.0
    material.unit_price = 3
    db_session.commit()
    assert client.get(summary_url()).json()["material_subtotal_known"] == 30.0


def test_database_error_is_generic_and_does_not_leak(
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
        "query",
        lambda *args: (_ for _ in ()).throw(
            OperationalError("SELECT private SQL", {}, Exception("database detail"))
        ),
    )
    response = client.get(summary_url())
    assert response.status_code == 500
    assert response.json() == {"detail": "Unable to read work budget"}
    assert rollback_calls == 1
    assert "private SQL" not in response.text
    assert "database detail" not in response.text
