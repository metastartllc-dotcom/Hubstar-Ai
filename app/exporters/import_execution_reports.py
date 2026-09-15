"""Deterministic execution reports without local absolute paths."""

import csv
import json
from pathlib import Path
from typing import Any, Iterable

from app.schemas.import_execution import ExecutionRow, ImportExecutionResult

EXECUTION_REPORT_FILENAMES = (
    "import-execution-summary.json",
    "work-master-import-result.csv",
    "work-item-import-result.csv",
    "material-import-result.csv",
    "import-execution-conflicts.csv",
)


def _csv(path: Path, fields: list[str], rows: Iterable[dict[str, Any]]) -> None:
    with path.open("x", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_execution_reports(report_dir: Path, result: ImportExecutionResult) -> list[str]:
    report_dir.mkdir(parents=True, exist_ok=False)
    targets = [report_dir / name for name in EXECUTION_REPORT_FILENAMES]
    with targets[0].open("x", encoding="utf-8", newline="\n") as output:
        json.dump(result.summary, output, ensure_ascii=False, indent=2, sort_keys=True)
        output.write("\n")
    fields = ["external_id", "action", "detail"]
    _csv(targets[1], fields, (row.to_dict() for row in sorted(result.work_master_rows, key=lambda r: r.external_id)))
    _csv(targets[2], fields, (row.to_dict() for row in sorted(result.work_item_rows, key=lambda r: r.external_id)))
    _csv(targets[3], fields, (row.to_dict() for row in sorted(result.material_rows, key=lambda r: r.external_id)))
    _csv(
        targets[4],
        ["entity_type", "external_id", "reason"],
        sorted(result.conflicts, key=lambda row: (row["entity_type"], row["external_id"])),
    )
    return [str(path.resolve()) for path in targets]
