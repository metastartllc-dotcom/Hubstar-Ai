"""Fail-closed orchestration for applying an approved unified preview."""

import json
import sqlite3
from pathlib import Path
from typing import Any

from app.exporters.import_execution_reports import EXECUTION_REPORT_FILENAMES, write_execution_reports
from app.importers.unified_excel_preview import file_sha256, run_preview, validate_report_directory
from app.repositories.unified_excel_import import ImportPersistenceError, execute_import_transaction
from app.schemas.import_execution import (
    IMPORT_CONFIRMATION,
    IMPORT_REVISION,
    ExecutionRow,
    ImportExecutionResult,
)


class ImportPreflightError(ValueError):
    pass


class ImportPostCommitError(RuntimeError):
    """The database commit succeeded, but final verification/reporting failed."""

    def __init__(self, message: str, result: ImportExecutionResult):
        super().__init__(message)
        self.result = result


def _failed_summary(workbook: Path, workbook_hash: str, database_hash: str,
                    project_id: str, reason: str, *, rollback: bool,
                    backup_info: dict[str, Any] | None = None) -> dict[str, Any]:
    backup_info = backup_info or {}
    return {
        "operation_mode": "APPLY", "status": "FAILED_ROLLED_BACK" if rollback else "FAILED",
        "source_dataset": "HUBSTAR_6R_7R_UNIFIED_2026",
        "workbook_filename": workbook.name, "workbook_sha256": workbook_hash,
        "pre_database_sha256": database_hash, "post_database_sha256": database_hash,
        "backup_filename": backup_info.get("filename"),
        "backup_sha256": backup_info.get("sha256"), "backup_size": backup_info.get("size"),
        "revision": IMPORT_REVISION, "project_id": project_id,
        "planned": {}, "created": {}, "linked": 0, "skipped": {},
        "rollback_performed": rollback, "database_writes_performed": False,
        "commit_completed": False,
        "import_batch_count": 0, "audit_log_count": 0,
        "failure_reason": reason,
        "excluded_scopes": ["equipment", "transport", "work_material_links"],
    }


def _require_absolute(path: Path, label: str) -> Path:
    if not path.is_absolute():
        raise ImportPreflightError(f"{label} must be an absolute path")
    return path.resolve()


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _database_state(path: Path) -> dict[str, Any]:
    try:
        connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
        connection.execute("PRAGMA query_only=ON")
        tables = [row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )]
        return {
            "revision": connection.execute("SELECT version_num FROM alembic_version").fetchone()[0],
            "quick_check": connection.execute("PRAGMA quick_check").fetchone()[0],
            "foreign_key_violations": len(connection.execute("PRAGMA foreign_key_check").fetchall()),
            "counts": {table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] for table in tables},
            "schema": [tuple(row) for row in connection.execute(
                "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"
            )],
            "protected_rows": {
                table: [tuple(row) for row in connection.execute(f'SELECT * FROM "{table}" ORDER BY 1')]
                for table in ("work_material_links", "equipments", "work_equipment_links", "transports")
                if table in tables
            },
            "total_changes": connection.total_changes,
        }
    except sqlite3.Error as exc:
        raise ImportPreflightError("Unable to inspect database") from exc
    finally:
        if "connection" in locals():
            connection.close()


def _validate_plan(plan: dict[str, Any], current: ImportExecutionResult | Any,
                   workbook: Path, database: Path, project_id: str) -> str:
    summary = current.summary
    if plan.get("project_id") != project_id:
        raise ImportPreflightError("Plan project does not match")
    source = plan.get("source_workbook", {})
    database_plan = plan.get("database", {})
    if Path(source.get("path", "")).resolve() != workbook:
        raise ImportPreflightError("Plan workbook does not match")
    if Path(database_plan.get("path", "")).resolve() != database:
        raise ImportPreflightError("Plan database does not match")
    if source.get("sha256_before") != summary["source_workbook"]["sha256_before"] or source.get("sha256_after") != summary["source_workbook"]["sha256_after"]:
        raise ImportPreflightError("Plan is stale or tampered: workbook hash")
    if database_plan.get("sha256_before") != summary["database"]["sha256_before"] or database_plan.get("sha256_after") != summary["database"]["sha256_after"]:
        raise ImportPreflightError("Plan is stale or tampered: database hash")
    if database_plan.get("sqlite_total_changes") != 0:
        raise ImportPreflightError("Plan database inspection was not read-only")
    for key in ("work_summary", "work_master_summary", "material_summary", "excluded_scopes"):
        if plan.get(key) != summary.get(key):
            raise ImportPreflightError(f"Plan is stale or tampered: {key}")
    plan_comparable = {key: value for key, value in plan.items() if key != "generated_at_utc"}
    current_comparable = {key: value for key, value in summary.items() if key != "generated_at_utc"}
    if plan_comparable != current_comparable:
        raise ImportPreflightError("Plan is stale or tampered")
    if plan.get("database_writes_performed") is not False:
        raise ImportPreflightError("Plan is not a dry-run plan")
    conflicts = (
        summary["work_summary"]["existing_conflict"]
        + summary["work_master_summary"]["existing_conflict"]
        + summary["work_master_summary"]["link_conflict"]
        + summary["material_summary"]["existing_conflict"]
    )
    if conflicts:
        raise ImportPreflightError("Import plan contains conflicts")
    initial = (
        summary["work_master_summary"]["create"] == 65
        and summary["work_summary"]["create"] == 64
        and summary["work_summary"]["existing_identical"] == 1
        and summary["work_master_summary"]["existing_work_link"] == 1
        and summary["material_summary"]["create"] == 980
        and summary["material_summary"]["existing_identical"] == 6
    )
    no_changes = (
        summary["work_master_summary"]["create"] == 0
        and summary["work_master_summary"]["existing_identical"] == 65
        and summary["work_summary"]["create"] == 0
        and summary["work_summary"]["existing_identical"] == 65
        and summary["work_master_summary"]["already_linked"] == 65
        and summary["material_summary"]["create"] == 0
        and summary["material_summary"]["existing_identical"] == 986
    )
    if not initial and not no_changes:
        raise ImportPreflightError("Import actions do not match an approved initial or no-change plan")
    return "NO_CHANGES" if no_changes else "APPLY"


def _create_verified_backup(source: Path, target: Path, expected_state: dict[str, Any]) -> dict[str, Any]:
    try:
        source_connection = sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)
        target_connection = sqlite3.connect(target)
        source_connection.execute("PRAGMA query_only=ON")
        source_connection.backup(target_connection)
    except (sqlite3.Error, OSError) as exc:
        raise ImportPreflightError("Unable to create or verify backup") from exc
    finally:
        if "target_connection" in locals():
            target_connection.close()
        if "source_connection" in locals():
            source_connection.close()
    backup_state = _database_state(target)
    if backup_state != expected_state:
        raise ImportPreflightError("Backup verification failed")
    return {"filename": target.name, "sha256": file_sha256(target), "size": target.stat().st_size}


def apply_unified_import(
    *, file_path: Path, project_id: str, database_path: Path, plan_path: Path,
    expected_workbook_sha256: str, expected_database_sha256: str,
    backup_path: Path, report_dir: Path, confirm: str,
    repository_root: Path | None = None,
) -> ImportExecutionResult:
    if confirm != IMPORT_CONFIRMATION:
        raise ImportPreflightError("Confirmation phrase does not match")
    root = (repository_root or Path(__file__).resolve().parents[2]).resolve()
    workbook = _require_absolute(file_path, "Workbook path")
    database = _require_absolute(database_path, "Database path")
    plan_file = _require_absolute(plan_path, "Plan path")
    backup = _require_absolute(backup_path, "Backup path")
    reports = _require_absolute(report_dir, "Report directory")
    for path, label in ((workbook, "Workbook"), (database, "Database"), (plan_file, "Plan")):
        if not path.is_file():
            raise ImportPreflightError(f"{label} does not exist")
    validate_report_directory(reports, root, workbook, database)
    if reports.exists():
        raise ImportPreflightError("Execution report directory must be new")
    if backup.exists() or backup == database:
        raise ImportPreflightError("Backup path must be new and different from the database")
    if not backup.parent.is_dir():
        raise ImportPreflightError("Backup parent directory does not exist")
    if _is_relative_to(backup, root) or backup.parent == database.parent:
        raise ImportPreflightError("Backup must be outside the repository and database directory")
    if any(Path(str(database) + suffix).exists() for suffix in ("-wal", "-shm")):
        raise ImportPreflightError("Database WAL/SHM sidecar exists; stop the server first")
    workbook_hash = file_sha256(workbook)
    database_hash = file_sha256(database)
    if workbook_hash != expected_workbook_sha256.upper():
        raise ImportPreflightError("Workbook SHA256 does not match")
    if database_hash != expected_database_sha256.upper():
        raise ImportPreflightError("Database SHA256 does not match")
    state_before = _database_state(database)
    if state_before["quick_check"] != "ok" or state_before["foreign_key_violations"] != 0:
        raise ImportPreflightError("Database integrity check failed")
    if state_before["revision"] != IMPORT_REVISION:
        raise ImportPreflightError("Database is not at the required Alembic revision")
    try:
        plan = json.loads(plan_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ImportPreflightError("Unable to read approved plan") from exc
    current = run_preview(
        file_path=workbook, project_id=project_id, database_path=database,
        report_dir=reports, repository_root=root, write_reports=False,
    )
    try:
        mode = _validate_plan(plan, current, workbook, database, project_id)
    except ImportPreflightError as exc:
        conflicts = []
        for row in current.work_rows:
            if row.master_action == "CONFLICT":
                conflicts.append({"entity_type": "work_master", "external_id": row.work_master_id,
                                  "reason": row.master_conflict_reason})
            if row.action == "CONFLICT" or row.master_link_action == "CONFLICT":
                conflicts.append({"entity_type": "work_item", "external_id": row.canonical_work_id,
                                  "reason": row.conflict_reason or row.master_link_conflict_reason})
        for row in current.material_rows:
            if row.action == "CONFLICT":
                conflicts.append({"entity_type": "material", "external_id": row.material_id,
                                  "reason": row.conflict_reason})
        if conflicts:
            failed = ImportExecutionResult(
                _failed_summary(
                    workbook, workbook_hash, database_hash, project_id,
                    "Import plan contains conflicts", rollback=False,
                ),
                conflicts=conflicts,
            )
            write_execution_reports(reports, failed)
        raise

    if mode == "NO_CHANGES":
        summary = {
            "operation_mode": "APPLY", "status": "NO_CHANGES",
            "source_dataset": "HUBSTAR_6R_7R_UNIFIED_2026",
            "workbook_filename": workbook.name, "workbook_sha256": workbook_hash,
            "pre_database_sha256": database_hash, "post_database_sha256": database_hash,
            "backup_filename": None, "backup_sha256": None, "backup_size": None,
            "revision": IMPORT_REVISION, "project_id": project_id,
            "planned": {"work_masters": 0, "work_items": 0, "materials": 0},
            "created": {"work_masters": 0, "work_items": 0, "materials": 0},
            "linked": 0, "skipped": {"work_masters": 65, "work_items": 65, "materials": 986},
            "rollback_performed": False, "database_writes_performed": False,
            "commit_completed": False,
            "import_batch_count": 0, "audit_log_count": 0,
            "excluded_scopes": ["equipment", "transport", "work_material_links"],
        }
        result = ImportExecutionResult(summary=summary)
        paths = write_execution_reports(reports, result)
        return ImportExecutionResult(summary, report_paths=paths)

    backup_info = _create_verified_backup(database, backup, state_before)
    try:
        master_rows, work_rows, material_rows, metadata = execute_import_transaction(
            database, workbook, project_id, workbook.name, workbook_hash,
            current.work_rows, current.material_rows,
            database_hash, workbook_hash,
        )
    except ImportPersistenceError:
        failed = ImportExecutionResult(
            _failed_summary(
                workbook, workbook_hash, database_hash, project_id,
                "Import transaction failed", rollback=True, backup_info=backup_info,
            )
        )
        write_execution_reports(reports, failed)
        raise
    def committed_failure(reason: str) -> ImportPostCommitError:
        post_hash = file_sha256(database)
        summary = {
            "operation_mode": "APPLY", "status": "COMMITTED_VERIFICATION_FAILED",
            "source_dataset": "HUBSTAR_6R_7R_UNIFIED_2026",
            "workbook_filename": workbook.name, "workbook_sha256": workbook_hash,
            "pre_database_sha256": database_hash, "post_database_sha256": post_hash,
            "backup_filename": backup_info["filename"], "backup_sha256": backup_info["sha256"],
            "backup_size": backup_info["size"], "revision": IMPORT_REVISION,
            "project_id": project_id, "planned": {"work_masters": 65, "work_items": 64, "materials": 980},
            "created": {"work_masters": 65, "work_items": 64, "materials": 980},
            "linked": 1, "skipped": {"work_masters": 0, "work_items": 1, "materials": 6},
            "rollback_performed": False, "database_writes_performed": True,
            "commit_completed": True, "import_batch_count": metadata["import_batches"],
            "audit_log_count": metadata["audit_logs"], "failure_reason": reason,
            "excluded_scopes": ["equipment", "transport", "work_material_links"],
        }
        result = ImportExecutionResult(summary, master_rows, work_rows, material_rows)
        return ImportPostCommitError(reason, result)

    try:
        post_state = _database_state(database)
    except Exception as exc:
        raise committed_failure("Post-commit verification failed") from exc
    expected_counts = {
        "work_masters": 65, "work_items": 65, "materials": 986,
        "work_material_links": 6, "equipments": 1, "work_equipment_links": 1,
        "projects": 1, "transports": 0,
    }
    if any(post_state["counts"].get(table) != count for table, count in expected_counts.items()):
        raise committed_failure("Post-commit row-count verification failed")
    if post_state["quick_check"] != "ok" or post_state["foreign_key_violations"]:
        raise committed_failure("Post-commit integrity verification failed")
    if post_state["revision"] != IMPORT_REVISION:
        raise committed_failure("Post-commit revision verification failed")
    if post_state["protected_rows"] != state_before["protected_rows"]:
        raise committed_failure("Excluded-scope rows changed unexpectedly")
    try:
        connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
        try:
            connection.execute("PRAGMA query_only=ON")
            checks = {
                "unique_sources": connection.execute(
                    "SELECT COUNT(DISTINCT source_dataset || ':' || source_work_id) FROM work_masters"
                ).fetchone()[0],
                "master_refs": connection.execute(
                    "SELECT COUNT(*) FROM work_items WHERE work_master_ref_id IS NOT NULL"
                ).fetchone()[0],
                "dangling_refs": connection.execute(
                    "SELECT COUNT(*) FROM work_items wi LEFT JOIN work_masters wm ON wm.id=wi.work_master_ref_id "
                    "WHERE wi.work_master_ref_id IS NULL OR wm.id IS NULL"
                ).fetchone()[0],
                "active_materials": connection.execute("SELECT COUNT(*) FROM materials WHERE status='ACTIVE'").fetchone()[0],
                "review_materials": connection.execute("SELECT COUNT(*) FROM materials WHERE status='NEEDS_REVIEW'").fetchone()[0],
                "missing_prices": connection.execute("SELECT COUNT(*) FROM materials WHERE unit_price IS NULL").fetchone()[0],
            }
        finally:
            connection.close()
    except sqlite3.Error as exc:
        raise committed_failure("Post-commit domain verification failed") from exc
    if checks != {"unique_sources": 65, "master_refs": 65, "dangling_refs": 0,
                  "active_materials": 818, "review_materials": 168, "missing_prices": 168}:
        raise committed_failure("Post-commit domain invariant failed")
    post_hash = file_sha256(database)
    summary = {
        "operation_mode": "APPLY", "status": "SUCCESS",
        "source_dataset": "HUBSTAR_6R_7R_UNIFIED_2026",
        "workbook_filename": workbook.name, "workbook_sha256": workbook_hash,
        "pre_database_sha256": database_hash, "post_database_sha256": post_hash,
        "backup_filename": backup_info["filename"], "backup_sha256": backup_info["sha256"],
        "backup_size": backup_info["size"], "revision": IMPORT_REVISION,
        "project_id": project_id,
        "planned": {"work_masters": 65, "work_items": 64, "materials": 980},
        "created": {"work_masters": 65, "work_items": 64, "materials": 980},
        "linked": 1, "skipped": {"work_masters": 0, "work_items": 1, "materials": 6},
        "rollback_performed": False, "database_writes_performed": True,
        "commit_completed": True,
        "import_batch_count": metadata["import_batches"], "audit_log_count": metadata["audit_logs"],
        "excluded_scopes": ["equipment", "transport", "work_material_links"],
    }
    result = ImportExecutionResult(summary, master_rows, work_rows, material_rows)
    try:
        paths = write_execution_reports(reports, result)
    except Exception as exc:
        raise committed_failure("Post-commit execution report export failed") from exc
    return ImportExecutionResult(summary, master_rows, work_rows, material_rows, report_paths=paths)
