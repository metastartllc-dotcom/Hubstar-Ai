"""Read-only database access for work budget summaries."""

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.models import Material, Project, WorkItem, WorkMaterialLink
from app.services.material_calculator import current_calculated_quantity
from app.services.work_budget_summary import (
    MaterialBudgetInput,
    summarize_work_budget,
)


class SummaryProjectNotFoundError(Exception):
    """Raised when an external project ID is unknown."""


class SummaryWorkNotFoundError(Exception):
    """Raised when work is unknown or outside the URL project."""


class WorkBudgetSummaryPersistenceError(Exception):
    """Raised when a summary read fails."""


def get_work_budget_summary(db: Session, project_id: str, work_id: str) -> dict:
    """Read stable linked inputs and return their pure budget aggregation."""
    try:
        project = db.query(Project).filter(Project.project_id == project_id).first()
        if project is None:
            raise SummaryProjectNotFoundError
        work = db.query(WorkItem).filter(WorkItem.work_id == work_id).first()
        if work is None or work.project_id != project.id:
            raise SummaryWorkNotFoundError
        rows = (
            db.query(WorkMaterialLink, Material)
            .join(Material, Material.id == WorkMaterialLink.material_id)
            .filter(WorkMaterialLink.work_id == work.id)
            .order_by(WorkMaterialLink.id)
            .all()
        )
        inputs = [
            MaterialBudgetInput(
                material_id=material.material_id,
                calculated_quantity=current_calculated_quantity(
                    work.quantity, link.consumption_rate, link.waste_percentage,
                    link.calculated_quantity,
                ),
                approved_quantity=link.approved_quantity,
                unit_price=material.unit_price,
                link_status=link.status.value,
                material_status=material.status.value,
            )
            for link, material in rows
        ]
        totals = summarize_work_budget(work.labor_total, inputs)
        return {
            "project_id": project.project_id,
            "work_id": work.work_id,
            "name": work.name,
            "unit": work.unit,
            "quantity": work.quantity,
            "labor_unit_rate": work.labor_unit_rate,
            "labor_total": work.labor_total,
            "material_link_count": totals.material_link_count,
            "priced_material_count": totals.priced_material_count,
            "missing_price_count": totals.missing_price_count,
            "needs_review_count": totals.needs_review_count,
            "material_subtotal_known": float(totals.material_subtotal_known),
            "subtotal_known_before_vat": float(totals.subtotal_known_before_vat),
            "is_pricing_complete": totals.is_pricing_complete,
            "has_review_warnings": totals.has_review_warnings,
            "pricing_status": totals.pricing_status,
            "missing_price_material_ids": totals.missing_price_material_ids,
            "needs_review_material_ids": totals.needs_review_material_ids,
            "warnings": totals.warnings,
        }
    except (SummaryProjectNotFoundError, SummaryWorkNotFoundError):
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise WorkBudgetSummaryPersistenceError from exc
