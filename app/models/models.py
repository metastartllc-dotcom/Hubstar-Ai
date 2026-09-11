from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Date, Boolean, CheckConstraint, Enum, UniqueConstraint
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

class WorkMaster(Base):
    __tablename__ = "work_masters"
    __table_args__ = (
        UniqueConstraint("source_dataset", "source_work_id", name="uq_work_master_source"),
        CheckConstraint(
            "(source_dataset IS NULL AND source_work_id IS NULL) OR "
            "(source_dataset IS NOT NULL AND source_work_id IS NOT NULL)",
            name="ck_work_master_source_pair",
        ),
    )
    id = Column(Integer, primary_key=True, index=True)
    work_master_id = Column(String, nullable=False, unique=True, index=True)
    name = Column(String, nullable=False)
    category = Column(String)
    default_unit = Column(String)
    default_labor_unit_rate = Column(Float)
    status = Column(Enum(StatusEnum), nullable=False, default=StatusEnum.ACTIVE)
    source_dataset = Column(String)
    source_work_id = Column(String)
    work_items = relationship("WorkItem", back_populates="work_master")

class WorkItem(Base):
    __tablename__ = "work_items"
    id = Column(Integer, primary_key=True, index=True)
    work_id = Column(String, unique=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    work_master_ref_id = Column(Integer, ForeignKey("work_masters.id"), nullable=True, index=True)
    wbs_code = Column(String)
    name = Column(String, nullable=False)
    unit = Column(String)
    quantity = Column(Float)
    labor_unit_rate = Column(Float)
    labor_total = Column(Float)
    status = Column(Enum(StatusEnum), default=StatusEnum.ACTIVE)
    work_master = relationship("WorkMaster", back_populates="work_items")

    @property
    def work_master_id(self):
        return self.work_master.work_master_id if self.work_master is not None else None

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
    operator_included = Column(Boolean)
    fuel_included = Column(Boolean)
    delivery_included = Column(Boolean)
    included_delivery_one_way_distance_km = Column(Float, nullable=True, default=None)
    tariff_type = Column(String)
    unit_rate = Column(Float)
    availability = Column(String)
    status = Column(Enum(StatusEnum), default=StatusEnum.ACTIVE)

class WorkEquipmentLink(Base):
    __tablename__ = "work_equipment_links"
    __table_args__ = (UniqueConstraint("work_item_id", "equipment_id", name="uq_work_equipment_link"),)
    id = Column(Integer, primary_key=True, index=True)
    work_item_id = Column(Integer, ForeignKey("work_items.id"), nullable=False, index=True)
    equipment_id = Column(Integer, ForeignKey("equipments.id"), nullable=False, index=True)
    usage_quantity = Column(Float, nullable=False)
    agreed_unit_rate = Column(Float)
    tariff_type_snapshot = Column(String)
    operator_included_snapshot = Column(Boolean, default=None)
    fuel_included_snapshot = Column(Boolean, default=None)
    delivery_included_snapshot = Column(Boolean, default=None)
    included_delivery_one_way_distance_km_snapshot = Column(Float)
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
