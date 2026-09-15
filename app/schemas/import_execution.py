"""Typed import execution results and safety constants."""

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

IMPORT_CONFIRMATION = "IMPORT 65 WORK MASTERS 64 WORK ITEMS 980 MATERIALS"
IMPORT_REVISION = "0004_work_masters"


@dataclass(frozen=True)
class ExecutionRow:
    external_id: str
    action: Literal["CREATED", "LINKED", "SKIPPED"]
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ImportExecutionResult:
    summary: dict[str, Any]
    work_master_rows: list[ExecutionRow] = field(default_factory=list)
    work_item_rows: list[ExecutionRow] = field(default_factory=list)
    material_rows: list[ExecutionRow] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    report_paths: list[str] = field(default_factory=list)
