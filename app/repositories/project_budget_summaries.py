"""Bounded-query, read-only project budget loading."""

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.models import Project, WorkItem, Material, WorkMaterialLink
from app.services.work_budget_summary import MaterialBudgetInput
from app.services.material_calculator import current_calculated_quantity
from app.services.project_budget_summary import ProjectWorkBudgetInput, summarize_project_budget


class ProjectBudgetNotFoundError(Exception):
    pass


class ProjectBudgetPersistenceError(Exception):
    pass


def get_project_budget_summary(db: Session, project_id: str) -> dict:
    try:
        with db.no_autoflush:
            project = db.query(Project).filter(Project.project_id == project_id).first()
            if project is None:
                raise ProjectBudgetNotFoundError
            works = db.query(WorkItem).filter(WorkItem.project_id == project.id).order_by(WorkItem.id).all()
            rows = (
                db.query(WorkMaterialLink, Material)
                .join(WorkItem, WorkItem.id == WorkMaterialLink.work_id)
                .join(Material, Material.id == WorkMaterialLink.material_id)
                .filter(WorkItem.project_id == project.id)
                .order_by(WorkItem.id, WorkMaterialLink.id).all()
            )
            grouped = {work.id: [] for work in works}
            work_by_id = {work.id: work for work in works}
            for link, material in rows:
                grouped[link.work_id].append(MaterialBudgetInput(
                    material_id=material.material_id,
                    calculated_quantity=current_calculated_quantity(
                        work_by_id[link.work_id].quantity, link.consumption_rate,
                        link.waste_percentage, link.calculated_quantity,
                    ),
                    approved_quantity=link.approved_quantity,
                    unit_price=material.unit_price,
                    link_status=link.status.value,
                    material_status=material.status.value,
                ))
            inputs = [ProjectWorkBudgetInput(
                work_id=work.work_id, name=work.name, unit=work.unit,
                quantity=work.quantity, labor_total=work.labor_total,
                status=work.status.value, materials=grouped[work.id],
            ) for work in works]
            return {"project_id": project.project_id, "name": project.name,
                    **summarize_project_budget(inputs)}
    except SQLAlchemyError as exc:
        db.rollback()
        raise ProjectBudgetPersistenceError from exc
