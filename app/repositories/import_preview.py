"""Strictly read-only SQLite access for import preview comparisons."""

import sqlite3
from pathlib import Path
from typing import Any

from app.schemas.import_preview import DatabaseSnapshot


class PreviewDatabaseError(ValueError):
    """Raised when the preview database cannot be safely inspected."""


def _rows_by_external_id(
    connection: sqlite3.Connection,
    query: str,
    key: str,
    parameters: tuple[Any, ...] = (),
) -> dict[str, dict[str, Any]]:
    return {
        str(row[key]): dict(row)
        for row in connection.execute(query, parameters).fetchall()
    }


def load_database_snapshot(database_path: Path, project_id: str) -> DatabaseSnapshot:
    """Load comparison data through SQLite URI mode=ro without ORM mutations."""
    path = database_path.resolve(strict=True)
    uri = f"{path.as_uri()}?mode=ro"
    try:
        connection = sqlite3.connect(uri, uri=True)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        project_row = connection.execute(
            "SELECT id, project_id, name FROM projects WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        if project_row is None:
            raise PreviewDatabaseError(f"Project not found: {project_id}")
        project = dict(project_row)
        work_items = _rows_by_external_id(
            connection,
            """
            SELECT work_id, name, unit, quantity, labor_unit_rate, status
            FROM work_items WHERE project_id = ? ORDER BY work_id
            """,
            "work_id",
            (project["id"],),
        )
        materials = _rows_by_external_id(
            connection,
            """
            SELECT material_id, name, specification, normalized_unit,
                   unit_price, status
            FROM materials ORDER BY material_id
            """,
            "material_id",
        )
        total_changes = connection.total_changes
        return DatabaseSnapshot(
            project=project,
            work_items=work_items,
            materials=materials,
            total_changes=total_changes,
        )
    except sqlite3.Error as exc:
        raise PreviewDatabaseError("Unable to read preview database") from exc
    finally:
        if "connection" in locals():
            connection.close()
