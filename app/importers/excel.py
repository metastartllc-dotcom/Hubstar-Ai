import pandas as pd
from typing import List, Dict
from sqlalchemy.orm import Session
from app.models.models import ImportBatch, WorkItem, Material, StatusEnum
from app.validators.units import UnitNormalizer
from datetime import datetime

class ExcelImporter:
    def __init__(self, db: Session, project_id: int, version: str, uploader: str):
        self.db = db
        self.project_id = project_id
        self.version = version
        self.uploader = uploader
        self.warnings = []

    def import_works(self, filepath: str) -> ImportBatch:
        df = pd.read_excel(filepath)
        
        batch = ImportBatch(
            filename=filepath,
            project_id=self.project_id,
            version=self.version,
            uploader=self.uploader
        )
        self.db.add(batch)
        
        try:
            for index, row in df.iterrows():
                work_id = str(row.get('work_id'))
                if not work_id:
                    self.warnings.append(f"Row {index+2}: Missing work_id")
                    continue
                
                raw_unit = row.get('unit')
                normalized_unit = UnitNormalizer.normalize(raw_unit)
                if raw_unit and not normalized_unit:
                     self.warnings.append(f"Row {index+2}: Unknown unit {raw_unit}")
                     status = StatusEnum.NEEDS_REVIEW
                else:
                     status = StatusEnum.ACTIVE

                work_item = WorkItem(
                    work_id=work_id,
                    project_id=self.project_id,
                    wbs_code=str(row.get('wbs_code', '')),
                    name=str(row.get('name', '')),
                    unit=normalized_unit,
                    quantity=float(row.get('quantity', 0.0)),
                    labor_unit_rate=float(row.get('labor_unit_rate', 0.0)),
                    status=status
                )
                self.db.add(work_item)
            
            self.db.commit()
            return batch
        except Exception as e:
            self.db.rollback()
            raise ValueError(f"Import failed: {str(e)}")
