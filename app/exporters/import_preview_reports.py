"""Deterministic JSON and UTF-8 BOM CSV output for import previews."""

import csv
import json
from pathlib import Path
from typing import Any, Iterable

from app.schemas.import_preview import MaterialPreviewRow, WorkPreviewRow


REPORT_FILENAMES = (
    "import-preview-summary.json",
    "work-import-preview.csv",
    "material-import-preview.csv",
    "material-price-review.csv",
    "import-conflicts.csv",
)


class PreviewReportError(ValueError):
    """Raised when preview reports cannot be written without overwriting data."""


def _write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, Any]]) -> None:
    with path.open("x", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_preview_reports(
    report_dir: Path,
    summary: dict[str, Any],
    work_rows: list[WorkPreviewRow],
    material_rows: list[MaterialPreviewRow],
) -> list[str]:
    """Create all preview reports, refusing any existing output file."""
    report_dir.mkdir(parents=True, exist_ok=True)
    targets = [report_dir / name for name in REPORT_FILENAMES]
    existing = [str(path) for path in targets if path.exists()]
    if existing:
        raise PreviewReportError(f"Report file already exists: {existing[0]}")

    with targets[0].open("x", encoding="utf-8", newline="\n") as output:
        json.dump(summary, output, ensure_ascii=False, indent=2, sort_keys=True)
        output.write("\n")

    work_fields = [
        "source_work_id", "canonical_work_id", "name", "unit", "quantity",
        "labor_unit_rate", "proposed_status", "action", "conflict_reason",
        "source_row", "category",
    ]
    material_fields = [
        "material_id", "name", "normalized_unit", "specification", "category",
        "source_price", "source_price_kind", "existing_db_price",
        "proposed_unit_price", "candidate_price", "price_resolution",
        "proposed_status", "semantic_duplicate_group", "action",
        "conflict_reason", "source_row",
    ]
    _write_csv(targets[1], work_fields, (row.to_dict() for row in work_rows))
    _write_csv(targets[2], material_fields, (row.to_dict() for row in material_rows))
    _write_csv(
        targets[3],
        material_fields,
        (row.to_dict() for row in material_rows if row.action == "REVIEW"),
    )

    conflicts = [
        {
            "entity_type": "work",
            "external_id": row.canonical_work_id,
            "action": row.action,
            "conflict_reason": row.conflict_reason,
            "source_row": row.source_row,
        }
        for row in work_rows
        if row.action in {"CONFLICT", "INVALID"}
    ]
    conflicts.extend(
        {
            "entity_type": "material",
            "external_id": row.material_id,
            "action": row.action,
            "conflict_reason": row.conflict_reason,
            "source_row": row.source_row,
        }
        for row in material_rows
        if row.action in {"CONFLICT", "INVALID"}
    )
    conflicts.sort(key=lambda row: (row["entity_type"], row["external_id"]))
    _write_csv(
        targets[4],
        ["entity_type", "external_id", "action", "conflict_reason", "source_row"],
        conflicts,
    )
    return [str(path.resolve()) for path in targets]
