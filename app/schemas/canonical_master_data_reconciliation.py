"""Typed records for canonical workbook/production reconciliation."""

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class EntityReconciliationRow:
    entity_type: str
    external_id: str
    action: str
    workbook_present: bool
    production_present: bool
    source_identity: str
    explicit_diffs: str
    resolution_policy: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AliasReconciliationRow:
    entity_type: str
    alias_id: str
    canonical_id: str
    action: str
    reason: str
    validation_issues: str
    interpretation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RecipeReadinessRow:
    work_master_id: str
    material_id: str
    source_status: str
    internal_validation: str
    internal_issues: str
    workbook_work_reference: bool
    workbook_material_reference: bool
    work_production_reference: bool
    material_production_reference: bool
    semantic_match: str
    unit_match: str
    unit_issues: str
    dependency_actions: str
    readiness: str
    importable: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProtectedDataRow:
    entity_type: str
    external_id: str
    snapshot_json: str
    protection_policy: str = "UNCHANGED_READ_ONLY"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProductionSnapshot:
    revision: str
    work_masters: dict[str, dict[str, Any]]
    materials: dict[str, dict[str, Any]]
    protected_rows: tuple[ProtectedDataRow, ...]
    total_changes: int = 0


@dataclass(frozen=True)
class ReconciliationResult:
    summary: dict[str, Any]
    work_rows: list[EntityReconciliationRow] = field(default_factory=list)
    material_rows: list[EntityReconciliationRow] = field(default_factory=list)
    alias_rows: list[AliasReconciliationRow] = field(default_factory=list)
    recipe_rows: list[RecipeReadinessRow] = field(default_factory=list)
    protected_rows: list[ProtectedDataRow] = field(default_factory=list)
    report_paths: list[str] = field(default_factory=list)
