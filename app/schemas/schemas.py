from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from app.models.models import StatusEnum

class OrganizationBase(BaseModel):
    organization_id: Optional[str] = None
    master_id: Optional[str] = None
    name: str
    registration_number: Optional[str] = None
    participant_type: Optional[str] = None
    contact_information: Optional[str] = None
    status: StatusEnum = StatusEnum.ACTIVE

class OrganizationCreate(OrganizationBase):
    pass

class OrganizationResponse(OrganizationBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class ProjectBase(BaseModel):
    project_id: Optional[str] = None
    name: str
    location: Optional[str] = None
    project_type: Optional[str] = None
    gross_floor_area: Optional[float] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: StatusEnum = StatusEnum.ACTIVE
    owner_organization_id: Optional[int] = None
    contractor_organization_id: Optional[int] = None

class ProjectCreate(ProjectBase):
    pass

class ProjectResponse(ProjectBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class WorkItemBase(BaseModel):
    work_id: Optional[str] = None
    project_id: Optional[int] = None
    wbs_code: Optional[str] = None
    name: str
    unit: Optional[str] = None
    quantity: Optional[float] = None
    labor_unit_rate: Optional[float] = None
    labor_total: Optional[float] = None
    status: StatusEnum = StatusEnum.ACTIVE

class WorkItemCreate(WorkItemBase):
    pass

class WorkItemResponse(WorkItemBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class MaterialBase(BaseModel):
    material_id: Optional[str] = None
    master_id: Optional[str] = None
    code: Optional[str] = None
    name: str
    specification: Optional[str] = None
    normalized_unit: Optional[str] = None
    supplier_id: Optional[int] = None
    unit_price: Optional[float] = None
    status: StatusEnum = StatusEnum.ACTIVE

class MaterialCreate(MaterialBase):
    pass

class MaterialResponse(MaterialBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class WorkMaterialLinkBase(BaseModel):
    work_id: Optional[int] = None
    material_id: Optional[int] = None
    consumption_rate: Optional[float] = None
    waste_percentage: Optional[float] = None
    calculated_quantity: Optional[float] = None
    approved_quantity: Optional[float] = None
    status: StatusEnum = StatusEnum.ACTIVE

class WorkMaterialLinkCreate(WorkMaterialLinkBase):
    pass

class WorkMaterialLinkResponse(WorkMaterialLinkBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class EquipmentBase(BaseModel):
    equipment_id: Optional[str] = None
    master_id: Optional[str] = None
    type: Optional[str] = None
    model: Optional[str] = None
    capacity: Optional[str] = None
    location: Optional[str] = None
    operator_included: bool = False
    fuel_included: bool = False
    delivery_included: bool = False
    tariff_type: Optional[str] = None
    unit_rate: Optional[float] = None
    availability: Optional[str] = None
    status: StatusEnum = StatusEnum.ACTIVE

class EquipmentCreate(EquipmentBase):
    pass

class EquipmentResponse(EquipmentBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class TransportBase(BaseModel):
    transport_id: Optional[str] = None
    vehicle_type: Optional[str] = None
    payload_kg: Optional[float] = None
    volume_m3: Optional[float] = None
    route: Optional[str] = None
    one_way_distance_km: Optional[float] = None
    tariff: Optional[float] = None
    road_fee: Optional[float] = None
    multiplier: Optional[float] = None
    availability: Optional[str] = None
    conditions: Optional[str] = None

class TransportCreate(TransportBase):
    pass

class TransportResponse(TransportBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class ImportBatchBase(BaseModel):
    filename: str
    import_date: Optional[datetime] = None
    project_id: Optional[int] = None
    version: Optional[str] = None
    uploader: Optional[str] = None

class ImportBatchCreate(ImportBatchBase):
    pass

class ImportBatchResponse(ImportBatchBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class AuditLogBase(BaseModel):
    user: Optional[str] = None
    timestamp: Optional[datetime] = None
    entity_name: Optional[str] = None
    entity_id: Optional[int] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    source: Optional[str] = None
    reason: Optional[str] = None
    approval_status: Optional[str] = None

class AuditLogCreate(AuditLogBase):
    pass

class AuditLogResponse(AuditLogBase):
    id: int
    model_config = ConfigDict(from_attributes=True)
