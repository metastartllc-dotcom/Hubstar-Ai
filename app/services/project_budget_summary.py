"""Pure project aggregation, reusing the per-work budget rules."""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from app.services.work_budget_summary import EquipmentBudgetInput, MaterialBudgetInput, summarize_work_budget


@dataclass(frozen=True)
class ProjectWorkBudgetInput:
    work_id: str
    name: str
    unit: str | None
    quantity: float | None
    labor_total: float | None
    status: str
    materials: list[MaterialBudgetInput]
    equipment: list[EquipmentBudgetInput]


def summarize_project_budget(works: list[ProjectWorkBudgetInput]) -> dict:
    """Aggregate ordered work/link occurrences, never quantities."""
    labor = Decimal("0.00")
    material = Decimal("0.00")
    complete = incomplete = review = 0
    link_count = priced_count = missing_count = review_count = 0
    missing_labor = []
    no_materials = []
    missing_links = []
    review_links = []
    compact = []
    has_review = False
    equipment_subtotal = Decimal("0.00")
    equipment_link_count = equipment_priced = equipment_missing = equipment_review = equipment_excluded = 0
    missing_equipment_pairs = []
    review_equipment_pairs = []
    excluded_equipment_pairs = []
    equipment_warnings = []
    for work in works:
        totals = summarize_work_budget(work.labor_total, work.materials, work.equipment)
        work_review = totals.has_review_warnings or work.status == "NEEDS_REVIEW"
        has_review = has_review or work_review
        if totals.pricing_status == "NO_MATERIALS":
            no_materials.append(work.work_id)
        if totals.pricing_status == "NO_MATERIALS" or not totals.is_pricing_complete:
            incomplete += 1
            work_status = "INCOMPLETE"
        elif work_review:
            review += 1
            work_status = "NEEDS_REVIEW"
        else:
            complete += 1
            work_status = totals.pricing_status
        if work.labor_total is None:
            missing_labor.append(work.work_id)
        else:
            labor += Decimal(str(work.labor_total)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        material += totals.material_subtotal_known
        equipment_subtotal += totals.equipment_subtotal_known
        link_count += totals.material_link_count
        priced_count += totals.priced_material_count
        missing_count += totals.missing_price_count
        review_count += totals.needs_review_count
        equipment_link_count += totals.equipment_link_count
        equipment_priced += totals.priced_equipment_link_count
        equipment_missing += totals.missing_equipment_rate_link_count
        equipment_review += totals.needs_review_equipment_link_count
        equipment_excluded += totals.excluded_equipment_link_count
        missing_equipment_pairs.extend({"work_id": work.work_id, "equipment_id": eid} for eid in totals.missing_equipment_rate_ids)
        review_equipment_pairs.extend({"work_id": work.work_id, "equipment_id": eid} for eid in totals.needs_review_equipment_ids)
        excluded_equipment_pairs.extend({"work_id": work.work_id, "equipment_id": eid} for eid in totals.excluded_equipment_ids)
        for item in work.equipment:
            if item.link_status in ("REJECTED", "SUPERSEDED"):
                equipment_warnings.append(f"Equipment excluded from budget: {work.work_id} / {item.equipment_id}")
                continue
            if item.agreed_unit_rate is None:
                equipment_warnings.append(f"Missing equipment rate: {work.work_id} / {item.equipment_id}")
            if item.link_status in ("NEEDS_REVIEW", "ACTIVE_WITH_WARNINGS"):
                equipment_warnings.append(f"Equipment needs review: {work.work_id} / {item.equipment_id}")
        missing_links.extend(
            {"work_id": work.work_id, "material_id": mid}
            for mid in totals.missing_price_material_ids
        )
        review_links.extend(
            {"work_id": work.work_id, "material_id": mid}
            for mid in totals.needs_review_material_ids
        )
        compact.append({
            "work_id": work.work_id, "name": work.name,
            "unit": work.unit, "quantity": work.quantity,
            "labor_total": None if work.labor_total is None else Decimal(str(work.labor_total)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "material_subtotal_known": totals.material_subtotal_known,
            "subtotal_known_before_vat": totals.subtotal_known_before_vat,
            "missing_price_count": totals.missing_price_count,
            "needs_review_count": totals.needs_review_count,
            "pricing_status": work_status,
            "equipment_subtotal_known": totals.equipment_subtotal_known,
            "equipment_link_count": totals.equipment_link_count,
            "priced_equipment_link_count": totals.priced_equipment_link_count,
            "missing_equipment_rate_link_count": totals.missing_equipment_rate_link_count,
            "needs_review_equipment_link_count": totals.needs_review_equipment_link_count,
            "excluded_equipment_link_count": totals.excluded_equipment_link_count,
        })
    status = (
        "NO_WORK_ITEMS" if not works else
        "INCOMPLETE" if incomplete else
        "NEEDS_REVIEW" if has_review else "COMPLETE"
    )
    return {
        "work_item_count": len(works),
        "complete_work_count": complete,
        "incomplete_work_count": incomplete,
        "needs_review_work_count": review,
        "missing_labor_work_count": len(missing_labor),
        "no_materials_work_count": len(no_materials),
        "no_materials_work_ids": no_materials,
        "material_link_count": link_count,
        "priced_material_link_count": priced_count,
        "missing_price_link_count": missing_count,
        "needs_review_link_count": review_count,
        "labor_subtotal_known": labor,
        "material_subtotal_known": material,
        "equipment_link_count": equipment_link_count,
        "priced_equipment_link_count": equipment_priced,
        "missing_equipment_rate_link_count": equipment_missing,
        "needs_review_equipment_link_count": equipment_review,
        "excluded_equipment_link_count": equipment_excluded,
        "equipment_subtotal_known": equipment_subtotal,
        "missing_equipment_rate_pairs": missing_equipment_pairs,
        "needs_review_equipment_pairs": review_equipment_pairs,
        "excluded_equipment_pairs": excluded_equipment_pairs,
        "warnings": equipment_warnings,
        "subtotal_known_before_vat": (labor + material + equipment_subtotal).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "is_pricing_complete": bool(works) and incomplete == 0,
        "has_review_warnings": has_review,
        "pricing_status": status,
        "missing_labor_work_ids": missing_labor,
        "missing_price_links": missing_links,
        "needs_review_links": review_links,
        "works": compact,
    }
