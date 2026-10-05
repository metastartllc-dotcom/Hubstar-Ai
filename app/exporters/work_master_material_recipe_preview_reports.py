"""Deterministic JSON and UTF-8 BOM CSV reports for recipe previews."""

import csv
import json
from pathlib import Path
from typing import Any, Iterable

from app.schemas.work_master_material_recipe_preview import (
    AliasPreviewRow,
    ProtectedProjectLinkRow,
    RecipePreviewRow,
)

REPORT_FILENAMES = (
    "work-master-material-recipe-summary.json",
    "work-master-material-recipe-preview.csv",
    "work-master-material-recipe-active.csv",
    "work-master-material-recipe-review.csv",
    "work-master-material-recipe-conflicts.csv",
    "material-alias-validation.csv",
    "protected-project-material-links.csv",
)


class RecipePreviewReportError(ValueError):
    """Raised when reports cannot be created without overwriting files."""


def _write_csv(path: Path, fields: list[str], rows: Iterable[dict[str, Any]]) -> None:
    with path.open("x", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_recipe_preview_reports(
    report_dir: Path,
    summary: dict[str, Any],
    recipe_rows: list[RecipePreviewRow],
    alias_rows: list[AliasPreviewRow],
    protected_links: list[ProtectedProjectLinkRow],
) -> list[str]:
    report_dir.mkdir(parents=True, exist_ok=True)
    targets = [report_dir / name for name in REPORT_FILENAMES]
    existing = next((path for path in targets if path.exists()), None)
    if existing is not None:
        raise RecipePreviewReportError(f"Report file already exists: {existing}")

    with targets[0].open("x", encoding="utf-8", newline="\n") as output:
        json.dump(summary, output, ensure_ascii=False, indent=2, sort_keys=True)
        output.write("\n")

    fields = list(RecipePreviewRow.__dataclass_fields__)
    ordered = sorted(recipe_rows, key=lambda row: (row.work_master_id, row.material_id))
    _write_csv(targets[1], fields, (row.to_dict() for row in ordered))
    _write_csv(targets[2], fields, (row.to_dict() for row in ordered if row.source_status == "ACTIVE"))
    _write_csv(targets[3], fields, (row.to_dict() for row in ordered if row.source_status == "NEEDS_REVIEW"))

    conflict_fields = ["entity_type", "external_id", "related_id", "conflict_reason"]
    conflicts = [
        {
            "entity_type": "RECIPE",
            "external_id": row.work_master_id,
            "related_id": row.material_id,
            "conflict_reason": row.internal_conflict_reason,
        }
        for row in ordered
        if row.internal_conflict_reason
    ]
    conflicts.extend(
        {
            "entity_type": "MATERIAL_ALIAS",
            "external_id": row.alias_id,
            "related_id": row.canonical_id,
            "conflict_reason": row.conflict_reason,
        }
        for row in alias_rows
        if row.validation_status == "INVALID"
    )
    conflicts.sort(key=lambda row: (row["entity_type"], row["external_id"], row["related_id"]))
    _write_csv(targets[4], conflict_fields, conflicts)
    _write_csv(
        targets[5],
        list(AliasPreviewRow.__dataclass_fields__),
        (row.to_dict() for row in sorted(alias_rows, key=lambda row: row.alias_id)),
    )
    _write_csv(
        targets[6],
        list(ProtectedProjectLinkRow.__dataclass_fields__),
        (row.to_dict() for row in sorted(
            protected_links,
            key=lambda row: (row.project_id, row.work_id, row.material_id),
        )),
    )
    return [str(path.resolve()) for path in targets]
