"""Single-transaction persistence for an approved unified import plan."""

import json
import math
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.models.models import AuditLog, ImportBatch, Material, Project, StatusEnum, WorkItem, WorkMaster
from app.schemas.import_execution import ExecutionRow
from app.schemas.import_preview import MaterialPreviewRow, WorkPreviewRow


class ImportPersistenceError(RuntimeError):
    pass


def _checkpoint(_name: str) -> None:
    """Test seam for proving rollback at multiple transaction stages."""


def _same(left, right) -> bool:
    if left is None or right is None:
        return left is right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(float(left), float(right), rel_tol=0, abs_tol=1e-9)
    return str(left).strip().casefold() == str(right).strip().casefold()


def _labor_total(quantity: float | None, rate: float | None) -> float | None:
    if quantity is None or rate is None:
        return None
    return float((Decimal(str(quantity)) * Decimal(str(rate))).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    ))


def execute_import_transaction(
    database_path: Path,
    workbook_path: Path,
    project_id: str,
    workbook_filename: str,
    workbook_hash: str,
    work_rows: list[WorkPreviewRow],
    material_rows: list[MaterialPreviewRow],
    expected_database_sha256: str,
    expected_workbook_sha256: str,
) -> tuple[list[ExecutionRow], list[ExecutionRow], list[ExecutionRow], dict[str, int]]:
    """Apply all approved domain and aggregate metadata changes atomically."""
    engine = create_engine(
        "sqlite:///" + database_path.as_posix(),
        connect_args={"check_same_thread": False},
    )
    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    @event.listens_for(engine, "begin")
    def _begin_immediate(connection):
        connection.exec_driver_sql("BEGIN IMMEDIATE")
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session: Session = session_factory()
    master_results: list[ExecutionRow] = []
    work_results: list[ExecutionRow] = []
    material_results: list[ExecutionRow] = []
    try:
        with session.begin():
            # BEGIN IMMEDIATE serializes writers before any plan-dependent read.
            from app.importers.unified_excel_preview import file_sha256
            if any(Path(str(database_path) + suffix).exists() for suffix in ("-wal", "-shm")):
                raise ImportPersistenceError("Database sidecar appeared after backup")
            if file_sha256(database_path) != expected_database_sha256:
                raise ImportPersistenceError("Database changed after backup")
            if file_sha256(workbook_path) != expected_workbook_sha256:
                raise ImportPersistenceError("Workbook changed after backup")
            project = session.query(Project).filter(Project.project_id == project_id).one()
            _checkpoint("before_domain")
            master_by_external: dict[str, WorkMaster] = {}
            for row in sorted(work_rows, key=lambda item: item.work_master_id):
                master = session.query(WorkMaster).filter(
                    WorkMaster.work_master_id == row.work_master_id
                ).one_or_none()
                if row.master_action == "CREATE":
                    if master is not None:
                        raise ImportPersistenceError("Work master changed after preflight")
                    master = WorkMaster(
                        work_master_id=row.work_master_id,
                        name=row.name,
                        category=row.category,
                        default_unit=row.unit,
                        default_labor_unit_rate=row.labor_unit_rate,
                        status=StatusEnum.ACTIVE,
                        source_dataset=row.source_dataset,
                        source_work_id=row.source_work_id,
                    )
                    session.add(master)
                    master_results.append(ExecutionRow(row.work_master_id, "CREATED"))
                elif row.master_action == "SKIP" and master is not None:
                    master_results.append(ExecutionRow(row.work_master_id, "SKIPPED", "existing identical"))
                else:
                    raise ImportPersistenceError("Work master plan is no longer applicable")
                master_by_external[row.work_master_id] = master
            _checkpoint("after_masters")

            for row in sorted(work_rows, key=lambda item: item.canonical_work_id):
                master = master_by_external[row.work_master_id]
                work = session.query(WorkItem).filter(WorkItem.work_id == row.canonical_work_id).one_or_none()
                if row.action == "CREATE" and row.master_link_action == "CREATE_WITH_MASTER":
                    if work is not None:
                        raise ImportPersistenceError("Project work changed after preflight")
                    work = WorkItem(
                        work_id=row.canonical_work_id,
                        project_id=project.id,
                        name=row.name,
                        unit=row.unit,
                        quantity=row.quantity,
                        labor_unit_rate=row.labor_unit_rate,
                        labor_total=_labor_total(row.quantity, row.labor_unit_rate),
                        status=StatusEnum(row.proposed_status),
                    )
                    work.work_master = master
                    session.add(work)
                    work_results.append(ExecutionRow(row.canonical_work_id, "CREATED"))
                elif row.action == "SKIP" and row.master_link_action == "LINK_EXISTING":
                    if work is None or work.project_id != project.id:
                        raise ImportPersistenceError("Existing project work disappeared")
                    expected = (row.name, row.unit, row.quantity, row.labor_unit_rate,
                                _labor_total(row.quantity, row.labor_unit_rate), row.proposed_status)
                    actual = (work.name, work.unit, work.quantity, work.labor_unit_rate,
                              work.labor_total, work.status.value)
                    if not all(_same(left, right) for left, right in zip(actual, expected)):
                        raise ImportPersistenceError("Existing work snapshot differs")
                    if work.work_master_ref_id is not None:
                        raise ImportPersistenceError("Existing work already references a master")
                    work.work_master = master
                    work_results.append(ExecutionRow(row.canonical_work_id, "LINKED"))
                elif row.action == "SKIP" and row.master_link_action == "SKIP":
                    if work is None or work.work_master is None or work.work_master.work_master_id != master.work_master_id:
                        raise ImportPersistenceError("Existing work master link differs")
                    work_results.append(ExecutionRow(row.canonical_work_id, "SKIPPED", "existing identical"))
                else:
                    raise ImportPersistenceError("Project work plan is no longer applicable")
            _checkpoint("after_work_items")

            for row in sorted(material_rows, key=lambda item: item.material_id):
                material = session.query(Material).filter(Material.material_id == row.material_id).one_or_none()
                if row.action in {"CREATE", "REVIEW"}:
                    if material is not None:
                        raise ImportPersistenceError("Material changed after preflight")
                    material = Material(
                        material_id=row.material_id,
                        name=row.name,
                        specification=row.specification,
                        normalized_unit=row.normalized_unit,
                        unit_price=row.proposed_unit_price,
                        status=StatusEnum(row.proposed_status),
                    )
                    session.add(material)
                    material_results.append(ExecutionRow(row.material_id, "CREATED"))
                elif row.action == "SKIP" and material is not None:
                    material_results.append(ExecutionRow(row.material_id, "SKIPPED", "existing identical"))
                else:
                    raise ImportPersistenceError("Material plan is no longer applicable")

            batch = ImportBatch(
                filename=workbook_filename,
                project_id=project.id,
                version="HUBSTAR_6R_7R_UNIFIED_2026",
                uploader="unified_excel_import",
                import_date=datetime.now(timezone.utc),
            )
            audit = AuditLog(
                user="system",
                entity_name="unified_master_data_import",
                source=workbook_filename,
                reason="approved unified master-data import",
                approval_status="APPLIED",
                new_value=json.dumps({
                    "source_dataset": "HUBSTAR_6R_7R_UNIFIED_2026",
                    "workbook_sha256": workbook_hash,
                    "work_masters_created": sum(row.action == "CREATED" for row in master_results),
                    "work_items_created": sum(row.action == "CREATED" for row in work_results),
                    "materials_created": sum(row.action == "CREATED" for row in material_results),
                }, sort_keys=True),
                timestamp=datetime.now(timezone.utc),
            )
            session.add_all([batch, audit])
            session.flush()
            invariants = {
                "work_masters": session.query(WorkMaster).count(),
                "work_items": session.query(WorkItem).count(),
                "work_refs": session.query(WorkItem).filter(WorkItem.work_master_ref_id.is_not(None)).count(),
                "materials": session.query(Material).count(),
                "active_materials": session.query(Material).filter(Material.status == StatusEnum.ACTIVE).count(),
                "review_materials": session.query(Material).filter(Material.status == StatusEnum.NEEDS_REVIEW).count(),
                "missing_prices": session.query(Material).filter(Material.unit_price.is_(None)).count(),
            }
            if invariants != {
                "work_masters": 65, "work_items": 65, "work_refs": 65,
                "materials": 986, "active_materials": 818,
                "review_materials": 168, "missing_prices": 168,
            }:
                raise ImportPersistenceError("Pre-commit domain invariant failed")
            _checkpoint("before_commit")
        metadata_counts = {"import_batches": 1, "audit_logs": 1}
        return master_results, work_results, material_results, metadata_counts
    except ImportPersistenceError:
        session.rollback()
        raise
    except SQLAlchemyError as exc:
        session.rollback()
        raise ImportPersistenceError("Unable to persist unified import") from exc
    finally:
        session.close()
        engine.dispose()
