"""Pure aggregation for a work item's known labor and material budget."""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


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


def _money(value: object) -> Decimal:
    return Decimal(str(value)).quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)


def summarize_work_budget(
    labor_total: object | None,
    materials: list[MaterialBudgetInput],
) -> WorkBudgetTotals:
    """Aggregate only known monetary amounts without combining quantities."""
    material_subtotal = Decimal("0.00")
    missing_ids: list[str] = []
    review_ids: list[str] = []
    warnings: list[str] = []
    priced_count = 0

    for material in materials:
        effective_quantity = (
            material.approved_quantity
            if material.approved_quantity is not None
            else material.calculated_quantity
        )
        material_total = None
        if effective_quantity is not None and material.unit_price is not None:
            material_total = _money(
                Decimal(str(effective_quantity)) * Decimal(str(material.unit_price))
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

    labor_known = labor_total is not None
    if not labor_known:
        warnings.insert(0, "Labor total is unavailable")
    subtotal = material_subtotal
    if labor_known:
        subtotal += _money(labor_total)

    pricing_complete = labor_known and not missing_ids
    has_review_warnings = bool(review_ids)
    if not materials:
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
    )
