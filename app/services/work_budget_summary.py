"""Pure aggregation for a work item's known labor and material budget."""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from app.services.equipment_calculator import calculate_equipment_total


MONEY_PLACES = Decimal("0.01")


@dataclass(frozen=True)
class MaterialBudgetInput:
    material_id: str
    calculated_quantity: object | None
    approved_quantity: object | None
    unit_price: object | None
    link_status: str
    material_status: str


@dataclass(frozen=True)
class EquipmentBudgetInput:
    equipment_id: str
    usage_quantity: object
    agreed_unit_rate: object | None
    link_status: str


@dataclass(frozen=True)
class WorkBudgetTotals:
    material_link_count: int
    priced_material_count: int
    missing_price_count: int
    needs_review_count: int
    material_subtotal_known: Decimal
    subtotal_known_before_vat: Decimal
    is_pricing_complete: bool
    has_review_warnings: bool
    pricing_status: str
    missing_price_material_ids: list[str]
    needs_review_material_ids: list[str]
    warnings: list[str]
    equipment_link_count: int
    priced_equipment_link_count: int
    missing_equipment_rate_link_count: int
    needs_review_equipment_link_count: int
    excluded_equipment_link_count: int
    equipment_subtotal_known: Decimal
    missing_equipment_rate_ids: list[str]
    needs_review_equipment_ids: list[str]
    excluded_equipment_ids: list[str]


def _money(value: object) -> Decimal:
    return Decimal(str(value)).quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)


def summarize_work_budget(
    labor_total: object | None,
    materials: list[MaterialBudgetInput],
    equipment: list[EquipmentBudgetInput] | None = None,
) -> WorkBudgetTotals:
    """Aggregate only known monetary amounts without combining quantities."""
    material_subtotal = Decimal("0.00")
    missing_ids: list[str] = []
    review_ids: list[str] = []
    warnings: list[str] = []
    priced_count = 0
    equipment = equipment or []

    for material in materials:
        effective_quantity = (
            material.approved_quantity
            if material.approved_quantity is not None
            else material.calculated_quantity
        )
        material_total = None
        if effective_quantity is not None and material.unit_price is not None:
            material_total = _money(
                Decimal(str(effective_quantity)).quantize(
                    Decimal("0.001"), rounding=ROUND_HALF_UP
                ) * Decimal(str(material.unit_price))
            )
        if material.unit_price is None or material_total is None:
            missing_ids.append(material.material_id)
            warnings.append(f"Missing material price: {material.material_id}")
        else:
            priced_count += 1
            material_subtotal += material_total

        if (
            material.link_status == "NEEDS_REVIEW"
            or material.material_status == "NEEDS_REVIEW"
        ):
            review_ids.append(material.material_id)
            warnings.append(f"Material needs review: {material.material_id}")

    equipment_subtotal = Decimal("0.00")
    equipment_priced = 0
    equipment_missing: list[str] = []
    equipment_review: list[str] = []
    equipment_excluded: list[str] = []
    for item in equipment:
        if item.link_status in ("REJECTED", "SUPERSEDED"):
            equipment_excluded.append(item.equipment_id)
            warnings.append(f"Equipment excluded from budget: {item.equipment_id}")
            continue
        total = None
        if item.agreed_unit_rate is not None:
            total = calculate_equipment_total(item.usage_quantity, item.agreed_unit_rate)
        if total is None:
            equipment_missing.append(item.equipment_id)
            warnings.append(f"Missing equipment rate: {item.equipment_id}")
        else:
            equipment_priced += 1
            equipment_subtotal += total
        if item.link_status in ("NEEDS_REVIEW", "ACTIVE_WITH_WARNINGS"):
            equipment_review.append(item.equipment_id)
            warnings.append(f"Equipment needs review: {item.equipment_id}")

    labor_known = labor_total is not None
    if not labor_known:
        warnings.insert(0, "Labor total is unavailable")
    subtotal = material_subtotal + equipment_subtotal
    if labor_known:
        subtotal += _money(labor_total)

    pricing_complete = labor_known and not missing_ids and not equipment_missing
    has_review_warnings = bool(review_ids or equipment_review or equipment_excluded)
    if not materials and not equipment_missing:
        pricing_status = "NO_MATERIALS"
    elif not pricing_complete:
        pricing_status = "INCOMPLETE"
    elif has_review_warnings:
        pricing_status = "NEEDS_REVIEW"
    else:
        pricing_status = "COMPLETE"

    return WorkBudgetTotals(
        material_link_count=len(materials),
        priced_material_count=priced_count,
        missing_price_count=len(missing_ids),
        needs_review_count=len(review_ids),
        material_subtotal_known=material_subtotal.quantize(
            MONEY_PLACES, rounding=ROUND_HALF_UP
        ),
        subtotal_known_before_vat=subtotal.quantize(
            MONEY_PLACES, rounding=ROUND_HALF_UP
        ),
        is_pricing_complete=pricing_complete,
        has_review_warnings=has_review_warnings,
        pricing_status=pricing_status,
        missing_price_material_ids=missing_ids,
        needs_review_material_ids=review_ids,
        warnings=warnings,
        equipment_link_count=len(equipment),
        priced_equipment_link_count=equipment_priced,
        missing_equipment_rate_link_count=len(equipment_missing),
        needs_review_equipment_link_count=len(equipment_review),
        excluded_equipment_link_count=len(equipment_excluded),
        equipment_subtotal_known=equipment_subtotal.quantize(MONEY_PLACES, rounding=ROUND_HALF_UP),
        missing_equipment_rate_ids=equipment_missing,
        needs_review_equipment_ids=equipment_review,
        excluded_equipment_ids=equipment_excluded,
    )
