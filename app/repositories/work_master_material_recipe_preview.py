"""Strictly read-only SQLite access for recipe preview comparisons."""

import sqlite3
from pathlib import Path

from app.schemas.work_master_material_recipe_preview import (
    ProtectedProjectLinkRow,
    RecipeDatabaseSnapshot,
)


class RecipePreviewDatabaseError(ValueError):
    """Raised when production readiness cannot be inspected safely."""


def load_recipe_database_snapshot(
    database_path: Path,
    project_id: str,
    protected_work_master_id: str = "WKM-000001",
) -> RecipeDatabaseSnapshot:
    """Read identifiers and protected links without opening a writable connection."""
    path = database_path.resolve(strict=True)
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()
        if revision is None:
            raise RecipePreviewDatabaseError("Database has no Alembic revision")
        work_ids = frozenset(
            str(row[0])
            for row in connection.execute(
                "SELECT work_master_id FROM work_masters ORDER BY work_master_id"
            )
        )
        material_ids = frozenset(
            str(row[0])
            for row in connection.execute(
                "SELECT material_id FROM materials ORDER BY material_id"
            )
        )
        rows = connection.execute(
            """
            SELECT p.project_id, wi.work_id, wm.work_master_id, m.material_id,
                   l.consumption_rate, l.waste_percentage,
                   l.calculated_quantity, l.approved_quantity, l.status
            FROM work_material_links AS l
            JOIN work_items AS wi ON wi.id = l.work_id
            JOIN projects AS p ON p.id = wi.project_id
            JOIN work_masters AS wm ON wm.id = wi.work_master_ref_id
            JOIN materials AS m ON m.id = l.material_id
            WHERE p.project_id = ? AND wm.work_master_id = ?
            ORDER BY wm.work_master_id, m.material_id
            """,
            (project_id, protected_work_master_id),
        ).fetchall()
        protected = tuple(
            ProtectedProjectLinkRow(
                project_id=str(row["project_id"]),
                work_id=str(row["work_id"]),
                work_master_id=str(row["work_master_id"]),
                material_id=str(row["material_id"]),
                consumption_rate=row["consumption_rate"],
                waste_percentage=row["waste_percentage"],
                calculated_quantity=row["calculated_quantity"],
                approved_quantity=row["approved_quantity"],
                link_status=row["status"],
            )
            for row in rows
        )
        return RecipeDatabaseSnapshot(
            revision=str(revision[0]),
            work_master_ids=work_ids,
            material_ids=material_ids,
            protected_links=protected,
            total_changes=connection.total_changes,
        )
    except sqlite3.Error as exc:
        raise RecipePreviewDatabaseError("Unable to read recipe preview database") from exc
    finally:
        if connection is not None:
            connection.close()
