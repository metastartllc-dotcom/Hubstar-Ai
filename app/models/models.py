from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Date, Boolean, Enum
from sqlalchemy.orm import relationship
import enum
from decimal import Decimal
from datetime import datetime
from app.core.database import Base

class StatusEnum(str, enum.Enum):
    VALID = "VALID"
    ACTIVE = "ACTIVE"
    ACTIVE_WITH_WARNINGS = "ACTIVE_WITH_WARNINGS"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"

class Organization(Base):
    __tablename__ = "organizations"
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(String, unique=True, index=True)
    master_id = Column(String, index=True)
    name = Column(String, nullable=False)
    registration_number = Column(String)
    participant_type = Column(String)
    contact_information = Column(String)
    status = Column(Enum(StatusEnum), default=StatusEnum.ACTIVE)

class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(String, unique=True, index=True)
    name = Column(String, nullable=False)
    location = Column(String)
    project_type = Column(String)
    gross_floor_area = Column(Float)
    start_date = Column(Date)
    end_date = Column(Date)
    status = Column(Enum(StatusEnum), default=StatusEnum.ACTIVE)
    owner_organization_id = Column(Integer, ForeignKey("organizations.id"))
    contractor_organization_id = Column(Integer, ForeignKey("organizations.id"))

class WorkItem(Base):
    __tablename__ = "work_items"
    id = Column(Integer, primary_key=True, index=True)
    work_id = Column(String, unique=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    wbs_code = Column(String)
    name = Column(String, nullable=False)
    unit = Column(String)
    quantity = Column(Float)
    labor_unit_rate = Column(Float)
    labor_total = Column(Float)
    status = Column(Enum(StatusEnum), default=StatusEnum.ACTIVE)

class Material(Base):
    __tablename__ = "materials"
    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(String, unique=True, index=True)
    master_id = Column(String, index=True)
    code = Column(String)
    name = Column(String, nullable=False)
    specification = Column(String)
    normalized_unit = Column(String)
    supplier_id = Column(Integer, ForeignKey("organizations.id"))
    unit_price = Column(Float)
    status = Column(Enum(StatusEnum), default=StatusEnum.ACTIVE)

class WorkMaterialLink(Base):
    __tablename__ = "work_material_links"
    id = Column(Integer, primary_key=True, index=True)
    work_id = Column(Integer, ForeignKey("work_items.id"))
    material_id = Column(Integer, ForeignKey("materials.id"))
    consumption_rate = Column(Float)
    waste_percentage = Column(Float)
    calculated_quantity = Column(Float)
    approved_quantity = Column(Float)
    status = Column(Enum(StatusEnum), default=StatusEnum.ACTIVE)

class Equipment(Base):
    __tablename__ = "equipments"
    id = Column(Integer, primary_key=True, index=True)
    equipment_id = Column(String, unique=True, index=True)
    master_id = Column(String, index=True)
    type = Column(String)
    model = Column(String)
    capacity = Column(String)
    location = Column(String)
    operator_included = Column(Boolean, default=False)
    fuel_included = Column(Boolean, default=False)
    delivery_included = Column(Boolean, default=False)
    tariff_type = Column(String)
    unit_rate = Column(Float)
    availability = Column(String)
    status = Column(Enum(StatusEnum), default=StatusEnum.ACTIVE)

class Transport(Base):
    __tablename__ = "transports"
    id = Column(Integer, primary_key=True, index=True)
    transport_id = Column(String, unique=True, index=True)
    vehicle_type = Column(String)
    payload_kg = Column(Float)
    volume_m3 = Column(Float)
    route = Column(String)
    one_way_distance_km = Column(Float)
    tariff = Column(Float)
    road_fee = Column(Float)
    multiplier = Column(Float)
    availability = Column(String)
    conditions = Column(String)

class ImportBatch(Base):
    __tablename__ = "import_batches"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    import_date = Column(DateTime, default=datetime.utcnow)
    project_id = Column(Integer, ForeignKey("projects.id"))
    version = Column(String)
    uploader = Column(String)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    user = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    entity_name = Column(String)
    entity_id = Column(Integer)
    old_value = Column(String)
    new_value = Column(String)
    source = Column(String)
    reason = Column(String)
    approval_status = Column(String)
