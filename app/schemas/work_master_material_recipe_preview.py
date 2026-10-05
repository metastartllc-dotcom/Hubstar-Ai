"""Typed records for the read-only Work Master material recipe preview."""

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

RecipeSourceStatus = Literal["ACTIVE", "NEEDS_REVIEW"]
RecipeAction = Literal["ACTIVE_PROPOSAL", "EXCLUDED_REVIEW", "INVALID"]
ProductionReadiness = Literal["READY", "PRODUCTION_NOT_READY"]


@dataclass(frozen=True)
class RecipePreviewRow:
    work_master_id: str
    material_id: str
    work_name: str
    material_name: str
    work_unit: str | None
    material_unit: str | None
    consumption_rate: float | None
    waste_percentage: float | None
    norm_with_waste: float | None
    source_material_qty: float | None
    base_work_qty: float | None
    source_status: RecipeSourceStatus
    action: RecipeAction
    internal_conflict_reason: str
    production_reference_status: ProductionReadiness
    production_readiness: ProductionReadiness
    production_readiness_reason: str
    source_dataset: str
    source_rows: str
    source_link_count: int
    unit_conversion_applied: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AliasPreviewRow:
    alias_id: str
    canonical_id: str
    reason: str
    validation_status: Literal["VALID", "INVALID"]
    conflict_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProtectedProjectLinkRow:
    project_id: str
    work_id: str
    work_master_id: str
    material_id: str
    consumption_rate: float | None
    waste_percentage: float | None
    calculated_quantity: float | None
    approved_quantity: float | None
    link_status: str | None
    protection_policy: str = "PRESERVE_PROJECT_SPECIFIC_LINK"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RecipeDatabaseSnapshot:
    revision: str
    work_master_ids: frozenset[str]
    material_ids: frozenset[str]
    protected_links: tuple[ProtectedProjectLinkRow, ...]
    total_changes: int = 0


@dataclass(frozen=True)
class RecipePreviewResult:
    summary: dict[str, Any]
    recipe_rows: list[RecipePreviewRow] = field(default_factory=list)
    alias_rows: list[AliasPreviewRow] = field(default_factory=list)
    protected_links: list[ProtectedProjectLinkRow] = field(default_factory=list)
    report_paths: list[str] = field(default_factory=list)
