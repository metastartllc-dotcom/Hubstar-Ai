import pandas as pd
from sqlalchemy.orm import Session
from datetime import datetime
import os

class ReportExporter:
    def __init__(self, db: Session):
        self.db = db

    def export_project_budget_csv(self, output_dir: str = "data/output") -> str:
        # Dummy query logic for now
        from app.models.models import WorkItem
        works = self.db.query(WorkItem).all()
        
        data = [{
            "Work ID": w.work_id,
            "Name": w.name,
            "Unit": w.unit,
            "Quantity": w.quantity,
            "Labor Rate": w.labor_unit_rate,
            "Status": w.status.value
        } for w in works]
        
        df = pd.DataFrame(data)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{output_dir}/project_budget_{timestamp}.csv"
        os.makedirs(output_dir, exist_ok=True)
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        return filename

    def export_project_budget_xlsx(self, output_dir: str = "data/output") -> str:
        from app.models.models import WorkItem
        works = self.db.query(WorkItem).all()
        
        data = [{
            "Work ID": w.work_id,
            "Name": w.name,
            "Unit": w.unit,
            "Quantity": w.quantity,
            "Labor Rate": w.labor_unit_rate,
            "Status": w.status.value
        } for w in works]
        
        df = pd.DataFrame(data)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{output_dir}/project_budget_{timestamp}.xlsx"
        os.makedirs(output_dir, exist_ok=True)
        df.to_excel(filename, index=False)
        return filename
