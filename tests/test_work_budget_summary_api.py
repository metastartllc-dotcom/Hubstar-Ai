import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.main import app
from app.core.database import Base, get_db
from app.models.models import Equipment, Material, Project, StatusEnum, WorkEquipmentLink, WorkItem, WorkMaterialLink


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


def add_equipment_link(db, work, external, *, rate=150000, usage=72,
                       status=StatusEnum.ACTIVE, master_rate=None):
    equipment = Equipment(equipment_id=external, type="Crane", unit_rate=rate if master_rate is None else master_rate,
                          tariff_type="MNT/hour", operator_included=True, fuel_included=True,
                          delivery_included=True, included_delivery_one_way_distance_km=25,
                          status=StatusEnum.ACTIVE)
    db.add(equipment); db.flush()
    db.add(WorkEquipmentLink(work_item_id=work.id, equipment_id=equipment.id,
                             usage_quantity=usage, agreed_unit_rate=rate,
                             tariff_type_snapshot="MNT/hour", status=status))
    db.commit(); return equipment


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
    assert response.json()["equipment_link_count"] == 0
    assert response.json()["equipment_subtotal_known"] == 0
    assert response.json()["missing_equipment_rate_ids"] == []


def test_equipment_snapshot_subtotal_and_master_change(client, db_session):
    _, work = seed_work(db_session, labor_total=255000000)
    add_link(db_session, work, "MAT", price=7114500, calculated=10)
    equipment = add_equipment_link(db_session, work, "CRANE")
    body = client.get(summary_url()).json()
    assert body["equipment_subtotal_known"] == 10800000
    assert body["subtotal_known_before_vat"] == 336945000
    assert body["priced_equipment_link_count"] == 1
    equipment.unit_rate = 200000; equipment.operator_included = False
    equipment.fuel_included = False; equipment.delivery_included = False
    equipment.included_delivery_one_way_distance_km = None; db_session.commit()
    assert client.get(summary_url()).json()["equipment_subtotal_known"] == 10800000
    link = db_session.query(WorkEquipmentLink).one(); link.agreed_unit_rate = 200000; db_session.commit()
    assert client.get(summary_url()).json()["equipment_subtotal_known"] == 14400000


@pytest.mark.parametrize("rate,usage,status,pricing,priced,missing,review,excluded", [
    (None, 1, StatusEnum.ACTIVE, "INCOMPLETE", 0, 1, 0, 0),
    (None, 1, StatusEnum.NEEDS_REVIEW, "INCOMPLETE", 0, 1, 1, 0),
    (None, 1, StatusEnum.ACTIVE_WITH_WARNINGS, "INCOMPLETE", 0, 1, 1, 0),
    (0, 1, StatusEnum.ACTIVE, "COMPLETE", 1, 0, 0, 0),
    (10, 0, StatusEnum.ACTIVE, "COMPLETE", 1, 0, 0, 0),
    (10, 1, StatusEnum.NEEDS_REVIEW, "NEEDS_REVIEW", 1, 0, 1, 0),
    (10, 1, StatusEnum.ACTIVE_WITH_WARNINGS, "NEEDS_REVIEW", 1, 0, 1, 0),
    (10, 1, StatusEnum.REJECTED, "NEEDS_REVIEW", 0, 0, 0, 1),
    (10, 1, StatusEnum.SUPERSEDED, "NEEDS_REVIEW", 0, 0, 0, 1),
    (None, 1, StatusEnum.REJECTED, "NEEDS_REVIEW", 0, 0, 0, 1),
])
def test_equipment_status_price_and_zero_policy(client, db_session, rate, usage, status,
                                                pricing, priced, missing, review, excluded):
    _, work = seed_work(db_session)
    add_link(db_session, work, "MAT", price=1, calculated=1)
    add_equipment_link(db_session, work, "E", rate=rate, usage=usage, status=status)
    body = client.get(summary_url()).json()
    assert body["pricing_status"] == pricing
    assert body["priced_equipment_link_count"] == priced
    assert body["missing_equipment_rate_link_count"] == missing
    assert body["needs_review_equipment_link_count"] == review
    assert body["excluded_equipment_link_count"] == excluded
    assert body["equipment_link_count"] == priced + missing + excluded


def test_no_material_missing_equipment_cannot_be_hidden(client, db_session):
    _, work = seed_work(db_session); add_equipment_link(db_session, work, "E", rate=None)
    body = client.get(summary_url()).json()
    assert body["pricing_status"] == "INCOMPLETE"
    assert body["material_link_count"] == 0
    assert body["missing_equipment_rate_link_count"] == 1
    assert body["warnings"] == ["Missing equipment rate: E"]


def test_multiple_equipment_decimal_totals_aggregate(client, db_session):
    _, work = seed_work(db_session, labor_total=0); add_link(db_session, work, "MAT", price=0)
    add_equipment_link(db_session, work, "E1", rate=2.345, usage=1)
    add_equipment_link(db_session, work, "E2", rate=2.345, usage=1)
    body = client.get(summary_url()).json()
    assert body["priced_equipment_link_count"] == 2
    assert body["equipment_subtotal_known"] == 4.70
    assert body["equipment_link_count"] == 2


def test_equipment_warning_order_and_public_ids(client, db_session):
    _, work = seed_work(db_session); add_link(db_session, work, "MAT", price=1)
    add_equipment_link(db_session, work, "E2", rate=None, status=StatusEnum.NEEDS_REVIEW)
    add_equipment_link(db_session, work, "E1", status=StatusEnum.REJECTED)
    body = client.get(summary_url()).json()
    assert body["missing_equipment_rate_ids"] == ["E2"]
    assert body["needs_review_equipment_ids"] == ["E2"]
    assert body["excluded_equipment_ids"] == ["E1"]
    assert body["warnings"][-3:] == ["Missing equipment rate: E2", "Equipment needs review: E2", "Equipment excluded from budget: E1"]
    assert not any(key in body for key in ("work_item_id", "equipment_id", "id"))


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
