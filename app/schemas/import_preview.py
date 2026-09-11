"""Typed records produced by the unified Excel import preview."""

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


PreviewAction = Literal["CREATE", "SKIP", "CONFLICT", "REVIEW", "INVALID"]


@dataclass(frozen=True)
class WorkPreviewRow:
    source_work_id: str
    work_master_id: str
    source_dataset: str
    canonical_work_id: str
    name: str
    unit: str | None
    quantity: float | None
    labor_unit_rate: float | None
    proposed_status: str
    action: PreviewAction
    conflict_reason: str = ""
    source_row: int = 0
    category: str | None = None
    master_action: PreviewAction = "CREATE"
    master_conflict_reason: str = ""
    master_link_action: str = "CREATE_WITH_MASTER"
    master_link_conflict_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MaterialPreviewRow:
    material_id: str
    name: str
    normalized_unit: str | None
    specification: str | None
    category: str | None
    source_price: float | None
    source_price_kind: str
    existing_db_price: float | None
    proposed_unit_price: float | None
    candidate_price: float | None
    price_resolution: str
    proposed_status: str
    semantic_duplicate_group: str
    action: PreviewAction
    conflict_reason: str = ""
    source_row: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DatabaseSnapshot:
    project: dict[str, Any]
    work_items: dict[str, dict[str, Any]]
    materials: dict[str, dict[str, Any]]
    total_changes: int = 0
    work_masters: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass(frozen=True)
class PreviewResult:
    summary: dict[str, Any]
    work_rows: list[WorkPreviewRow] = field(default_factory=list)
    material_rows: list[MaterialPreviewRow] = field(default_factory=list)
    report_paths: list[str] = field(default_factory=list)
