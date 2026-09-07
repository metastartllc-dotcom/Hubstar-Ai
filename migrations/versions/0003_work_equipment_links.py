"""Add snapshot equipment assignments for work items."""
from alembic import op
import sqlalchemy as sa

revision = "0003_work_equipment_links"
down_revision = "0002_equipment_delivery_distance"
branch_labels = None
depends_on = None
TABLE = "work_equipment_links"
INDEXES = {"ix_work_equipment_links_id", "ix_work_equipment_links_work_item_id", "ix_work_equipment_links_equipment_id"}
COLUMNS = {"id", "work_item_id", "equipment_id", "usage_quantity", "agreed_unit_rate",
           "tariff_type_snapshot", "operator_included_snapshot", "fuel_included_snapshot",
           "delivery_included_snapshot", "included_delivery_one_way_distance_km_snapshot", "status"}


def _validate_existing(inspector):
    columns = {c["name"]: c for c in inspector.get_columns(TABLE)}
    if set(columns) != COLUMNS or any(columns[n]["nullable"] for n in ("id", "work_item_id", "equipment_id", "usage_quantity")):
        raise RuntimeError("Existing work_equipment_links table has an incompatible column contract")
    fks = {(tuple(f["constrained_columns"]), f["referred_table"], tuple(f["referred_columns"]))
           for f in inspector.get_foreign_keys(TABLE)}
    if fks != {(('work_item_id',), 'work_items', ('id',)), (('equipment_id',), 'equipments', ('id',))}:
        raise RuntimeError("Existing work_equipment_links table has incompatible foreign keys")
    uniques = {tuple(u["column_names"]) for u in inspector.get_unique_constraints(TABLE)}
    if uniques != {("work_item_id", "equipment_id")}:
        raise RuntimeError("Existing work_equipment_links table lacks its composite unique constraint")
    indexes = {i["name"] for i in inspector.get_indexes(TABLE)}
    if indexes != INDEXES:
        raise RuntimeError("Existing work_equipment_links table lacks required indexes")


def upgrade():
    inspector = sa.inspect(op.get_bind())
    required = {"work_items", "equipments"}
    if not required.issubset(inspector.get_table_names()):
        raise RuntimeError("Existing schema is incomplete. Run 'python -m app.core.init_db' before Alembic.")
    if TABLE in inspector.get_table_names():
        _validate_existing(inspector)
        return
    status = sa.Enum("VALID", "ACTIVE", "ACTIVE_WITH_WARNINGS", "NEEDS_REVIEW", "REJECTED", "SUPERSEDED", name="statusenum")
    op.create_table(TABLE,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("work_item_id", sa.Integer(), nullable=False),
        sa.Column("equipment_id", sa.Integer(), nullable=False),
        sa.Column("usage_quantity", sa.Float(), nullable=False),
        sa.Column("agreed_unit_rate", sa.Float(), nullable=True),
        sa.Column("tariff_type_snapshot", sa.String(), nullable=True),
        sa.Column("operator_included_snapshot", sa.Boolean(), nullable=True),
        sa.Column("fuel_included_snapshot", sa.Boolean(), nullable=True),
        sa.Column("delivery_included_snapshot", sa.Boolean(), nullable=True),
        sa.Column("included_delivery_one_way_distance_km_snapshot", sa.Float(), nullable=True),
        sa.Column("status", status, nullable=True),
        sa.ForeignKeyConstraint(["equipment_id"], ["equipments.id"]),
        sa.ForeignKeyConstraint(["work_item_id"], ["work_items.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("work_item_id", "equipment_id", name="uq_work_equipment_link"))
    op.create_index("ix_work_equipment_links_id", TABLE, ["id"])
    op.create_index("ix_work_equipment_links_work_item_id", TABLE, ["work_item_id"])
    op.create_index("ix_work_equipment_links_equipment_id", TABLE, ["equipment_id"])


def downgrade():
    if TABLE in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table(TABLE)
