from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from typing import Literal, Optional, List
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from app.models.models import StatusEnum
from app.validators.units import UnitNormalizer

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
    project_id: str
    gross_floor_area: Optional[float] = Field(default=None, ge=0)

    @field_validator("project_id", "name", "location", "project_type", mode="before")
    @classmethod
    def strip_string_fields(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("project_id", "name")
    @classmethod
    def reject_empty_identifiers(cls, value):
        if value == "":
            raise ValueError("must not be empty")
        return value

class ProjectUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = None
    location: Optional[str] = None
    project_type: Optional[str] = None
    gross_floor_area: Optional[float] = Field(default=None, ge=0)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[StatusEnum] = None

    @model_validator(mode="before")
    @classmethod
    def require_update_fields(cls, data):
        if isinstance(data, dict):
            if not data:
                raise ValueError("at least one field is required")
            for field_name in ("name", "status"):
                if field_name in data and data[field_name] is None:
                    raise ValueError(f"{field_name} must not be null")
        return data

    @field_validator("name", "location", "project_type", mode="before")
    @classmethod
    def strip_non_empty_strings(cls, value):
        if isinstance(value, str):
            value = value.strip()
            if value == "":
                raise ValueError("must not be empty")
        return value

    @model_validator(mode="after")
    def validate_date_order(self):
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.start_date > self.end_date
        ):
            raise ValueError("start_date must be on or before end_date")
        return self

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

class ProjectWorkItemCreate(BaseModel):
    """Work item payload scoped to the project identified by the URL."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    work_id: str
    name: str
    wbs_code: Optional[str] = None
    unit: Optional[str] = None
    quantity: Optional[float] = Field(default=None, ge=0)
    labor_unit_rate: Optional[float] = Field(default=None, ge=0)
    status: StatusEnum = StatusEnum.ACTIVE

    @field_validator("work_id", "name", "wbs_code", mode="before")
    @classmethod
    def strip_non_empty_strings(cls, value):
        if isinstance(value, str):
            value = value.strip()
            if value == "":
                raise ValueError("must not be empty")
        return value

    @field_validator("unit", mode="before")
    @classmethod
    def normalize_non_empty_unit(cls, value):
        if isinstance(value, str):
            value = value.strip()
            if value == "":
                raise ValueError("must not be empty")
            return UnitNormalizer.normalize(value)
        return value

class ProjectWorkItemResponse(BaseModel):
    """Work item response without the internal project foreign key."""

    id: int
    work_id: str
    name: str
    wbs_code: Optional[str] = None
    unit: Optional[str] = None
    quantity: Optional[float] = None
    labor_unit_rate: Optional[float] = None
    labor_total: Optional[float] = None
    status: StatusEnum
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

class MaterialCreateRequest(BaseModel):
    """Public material creation payload without internal database IDs."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    material_id: str
    name: str
    master_id: Optional[str] = None
    code: Optional[str] = None
    specification: Optional[str] = None
    normalized_unit: Optional[str] = None
    unit_price: Optional[float] = Field(default=None, ge=0)
    status: StatusEnum = StatusEnum.ACTIVE

    @field_validator(
        "material_id",
        "name",
        "master_id",
        "code",
        "specification",
        mode="before",
    )
    @classmethod
    def strip_non_empty_strings(cls, value):
        if isinstance(value, str):
            value = value.strip()
            if value == "":
                raise ValueError("must not be empty")
        return value

    @field_validator("normalized_unit", mode="before")
    @classmethod
    def normalize_unit(cls, value):
        if isinstance(value, str):
            value = value.strip()
            if value == "":
                raise ValueError("must not be empty")
            return UnitNormalizer.normalize(value)
        return value


class MaterialUpdateRequest(BaseModel):
    """Partial public update without immutable or internal identifiers."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    name: Optional[str] = None
    master_id: Optional[str] = None
    code: Optional[str] = None
    specification: Optional[str] = None
    normalized_unit: Optional[str] = None
    unit_price: Optional[float] = Field(default=None, ge=0)
    status: Optional[StatusEnum] = None

    @model_validator(mode="before")
    @classmethod
    def require_update_fields(cls, data):
        if isinstance(data, dict):
            if not data:
                raise ValueError("at least one field is required")
            for field_name in ("name", "status"):
                if field_name in data and data[field_name] is None:
                    raise ValueError(f"{field_name} must not be null")
        return data

    @field_validator(
        "name",
        "master_id",
        "code",
        "specification",
        mode="before",
    )
    @classmethod
    def strip_non_empty_strings(cls, value):
        if isinstance(value, str):
            value = value.strip()
            if value == "":
                raise ValueError("must not be empty")
        return value

    @field_validator("normalized_unit", mode="before")
    @classmethod
    def normalize_unit(cls, value):
        if isinstance(value, str):
            value = value.strip()
            if value == "":
                raise ValueError("must not be empty")
            return UnitNormalizer.normalize(value)
        return value


class MaterialPublicResponse(BaseModel):
    """Public material representation without internal or supplier IDs."""

    material_id: str
    master_id: Optional[str] = None
    code: Optional[str] = None
    name: str
    specification: Optional[str] = None
    normalized_unit: Optional[str] = None
    unit_price: Optional[float] = None
    status: StatusEnum
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


class WorkMaterialCreateRequest(BaseModel):
    """Public request for linking material master data to a work item."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    material_id: str
    consumption_rate: float = Field(ge=0)
    waste_percentage: float = Field(default=0, ge=0)
    approved_quantity: Optional[float] = Field(default=None, ge=0)
    status: StatusEnum = StatusEnum.ACTIVE

    @field_validator("material_id", mode="before")
    @classmethod
    def strip_material_id(cls, value):
        if isinstance(value, str):
            value = value.strip()
            if value == "":
                raise ValueError("must not be empty")
        return value


class WorkMaterialUpdateRequest(BaseModel):
    """Explicitly supplied mutable link fields only."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    consumption_rate: Optional[float] = Field(default=None, ge=0)
    waste_percentage: Optional[float] = Field(default=None, ge=0)
    approved_quantity: Optional[float] = Field(default=None, ge=0)
    status: Optional[StatusEnum] = None

    @model_validator(mode="before")
    @classmethod
    def validate_patch(cls, data):
        if isinstance(data, dict):
            if not data:
                raise ValueError("at least one field is required")
            for field in ("consumption_rate", "waste_percentage", "status"):
                if field in data and data[field] is None:
                    raise ValueError(f"{field} must not be null")
        return data


class WorkMaterialPublicResponse(BaseModel):
    """Linked material response without internal database identifiers."""

    material_id: str
    name: str
    specification: Optional[str] = None
    normalized_unit: Optional[str] = None
    unit_price: Optional[float] = None
    consumption_rate: float
    waste_percentage: float
    calculated_quantity: float
    approved_quantity: Optional[float] = None
    effective_quantity: float
    material_total: Optional[float] = None
    status: StatusEnum


class WorkBudgetSummaryResponse(BaseModel):
    """Known work budget values without internal identifiers or VAT."""

    project_id: str
    work_id: str
    name: str
    unit: Optional[str] = None
    quantity: Optional[float] = None
    labor_unit_rate: Optional[float] = None
    labor_total: Optional[float] = None
    material_link_count: int
    priced_material_count: int
    missing_price_count: int
    needs_review_count: int
    material_subtotal_known: float
    subtotal_known_before_vat: float
    is_pricing_complete: bool
    has_review_warnings: bool
    pricing_status: Literal[
        "NO_MATERIALS", "COMPLETE", "NEEDS_REVIEW", "INCOMPLETE"
    ]
    missing_price_material_ids: List[str]
    needs_review_material_ids: List[str]
    warnings: List[str]


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
