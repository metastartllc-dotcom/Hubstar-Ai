"""Deterministic reports for canonical master-data reconciliation."""

import csv
import json
from pathlib import Path
from typing import Any, Iterable

from app.schemas.canonical_master_data_reconciliation import (
    AliasReconciliationRow, EntityReconciliationRow, ProtectedDataRow,
    RecipeReadinessRow,
)

REPORT_FILENAMES = (
    "canonical-master-data-reconciliation-summary.json",
    "work-master-reconciliation.csv",
    "material-reconciliation.csv",
    "alias-reconciliation.csv",
    "recipe-readiness.csv",
    "reconciliation-conflicts.csv",
    "protected-production-data.csv",
)


def _csv(path: Path, fields: list[str], rows: Iterable[dict[str, Any]]) -> None:
    with path.open("x", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_reconciliation_reports(
    directory: Path, summary: dict[str, Any], work_rows: list[EntityReconciliationRow],
    material_rows: list[EntityReconciliationRow], alias_rows: list[AliasReconciliationRow],
    recipe_rows: list[RecipeReadinessRow], protected_rows: list[ProtectedDataRow],
) -> list[str]:
    directory.mkdir(parents=True, exist_ok=True)
    targets = [directory / name for name in REPORT_FILENAMES]
    if any(path.exists() for path in targets):
        raise ValueError("Reconciliation report already exists")
    with targets[0].open("x", encoding="utf-8", newline="\n") as output:
        json.dump(summary, output, ensure_ascii=False, indent=2, sort_keys=True)
        output.write("\n")
    _csv(targets[1], list(EntityReconciliationRow.__dataclass_fields__), (row.to_dict() for row in work_rows))
    _csv(targets[2], list(EntityReconciliationRow.__dataclass_fields__), (row.to_dict() for row in material_rows))
    _csv(targets[3], list(AliasReconciliationRow.__dataclass_fields__), (row.to_dict() for row in alias_rows))
    _csv(targets[4], list(RecipeReadinessRow.__dataclass_fields__), (row.to_dict() for row in recipe_rows))
    conflicts = [
        {"entity_type": row.entity_type, "external_id": row.external_id, "reason": row.explicit_diffs}
        for row in work_rows + material_rows if row.action == "CONFLICT"
    ] + [
        {"entity_type": f"ALIAS:{row.entity_type}", "external_id": row.alias_id, "reason": row.validation_issues}
        for row in alias_rows if row.action == "CONFLICT"
    ] + [
        {"entity_type": "RECIPE", "external_id": f"{row.work_master_id}|{row.material_id}", "reason": row.internal_issues}
        for row in recipe_rows if row.internal_validation == "INVALID"
    ]
    conflicts.sort(key=lambda row: (row["entity_type"], row["external_id"]))
    _csv(targets[5], ["entity_type", "external_id", "reason"], conflicts)
    _csv(targets[6], list(ProtectedDataRow.__dataclass_fields__), (row.to_dict() for row in protected_rows))
    return [str(path.resolve()) for path in targets]
