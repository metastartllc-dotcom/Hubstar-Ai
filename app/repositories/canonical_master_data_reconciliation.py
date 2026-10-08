"""Read-only production snapshot for canonical master-data reconciliation."""

import json
import sqlite3
from pathlib import Path
from typing import Any

from app.schemas.canonical_master_data_reconciliation import (
    ProductionSnapshot,
    ProtectedDataRow,
)


class ReconciliationDatabaseError(ValueError):
    """Raised when the production snapshot cannot be read safely."""


def _rows_by_id(connection: sqlite3.Connection, query: str, key: str) -> dict[str, dict[str, Any]]:
    return {str(row[key]): dict(row) for row in connection.execute(query)}


def _json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def load_production_snapshot(database_path: Path, project_id: str) -> ProductionSnapshot:
    path = database_path.resolve(strict=True)
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()
        if revision is None:
            raise ReconciliationDatabaseError("Database has no Alembic revision")
        work_masters = _rows_by_id(connection, """
            SELECT work_master_id, name, category, default_unit,
                   default_labor_unit_rate, status, source_dataset, source_work_id
            FROM work_masters ORDER BY work_master_id
        """, "work_master_id")
        materials = _rows_by_id(connection, """
            SELECT material_id, master_id, code, name, specification,
                   normalized_unit, unit_price, status
            FROM materials ORDER BY material_id
        """, "material_id")
        protected: list[ProtectedDataRow] = []
        work = connection.execute("""
            SELECT wi.work_id, wm.work_master_id, wi.wbs_code, wi.name, wi.unit,
                   wi.quantity, wi.labor_unit_rate, wi.labor_total, wi.status
            FROM work_items wi JOIN projects p ON p.id=wi.project_id
            LEFT JOIN work_masters wm ON wm.id=wi.work_master_ref_id
            WHERE p.project_id=? AND wi.work_id=?
        """, (project_id, f"{project_id}-WRK-001")).fetchone()
        if work is not None:
            protected.append(ProtectedDataRow("FACADE_WORK_ITEM", str(work["work_id"]), _json(dict(work))))
        for row in connection.execute("""
            SELECT wi.work_id, m.material_id, m.unit_price, m.status AS material_status,
                   l.consumption_rate, l.waste_percentage, l.calculated_quantity,
                   l.approved_quantity, l.status AS link_status
            FROM work_material_links l JOIN work_items wi ON wi.id=l.work_id
            JOIN projects p ON p.id=wi.project_id JOIN materials m ON m.id=l.material_id
            WHERE p.project_id=? AND wi.work_id=? ORDER BY m.material_id
        """, (project_id, f"{project_id}-WRK-001")):
            protected.append(ProtectedDataRow("FACADE_MATERIAL_LINK", str(row["material_id"]), _json(dict(row))))
        for row in connection.execute("""
            SELECT equipment_id, master_id, type, model, capacity, location,
                   operator_included, fuel_included, delivery_included,
                   included_delivery_one_way_distance_km, tariff_type, unit_rate,
                   availability, status FROM equipments ORDER BY equipment_id
        """):
            protected.append(ProtectedDataRow("EQUIPMENT_MASTER", str(row["equipment_id"]), _json(dict(row))))
        for row in connection.execute("""
            SELECT wi.work_id, e.equipment_id, l.usage_quantity, l.agreed_unit_rate,
                   l.tariff_type_snapshot, l.operator_included_snapshot,
                   l.fuel_included_snapshot, l.delivery_included_snapshot,
                   l.included_delivery_one_way_distance_km_snapshot, l.status
            FROM work_equipment_links l JOIN work_items wi ON wi.id=l.work_item_id
            JOIN projects p ON p.id=wi.project_id JOIN equipments e ON e.id=l.equipment_id
            WHERE p.project_id=? ORDER BY wi.work_id,e.equipment_id
        """, (project_id,)):
            protected.append(ProtectedDataRow("WORK_EQUIPMENT_SNAPSHOT", str(row["equipment_id"]), _json(dict(row))))
        return ProductionSnapshot(
            revision=str(revision[0]), work_masters=work_masters, materials=materials,
            protected_rows=tuple(protected), total_changes=connection.total_changes,
        )
    except sqlite3.Error as exc:
        raise ReconciliationDatabaseError("Unable to read reconciliation database") from exc
    finally:
        if connection is not None:
            connection.close()
