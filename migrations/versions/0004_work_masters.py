"""Add reusable work masters and an optional project-work reference."""

from alembic import op
import sqlalchemy as sa

revision = "0004_work_masters"
down_revision = "0003_work_equipment_links"
branch_labels = None
depends_on = None

MASTER_TABLE = "work_masters"
REF_COLUMN = "work_master_ref_id"


def _validate_master_table(inspector):
    columns = {column["name"]: column for column in inspector.get_columns(MASTER_TABLE)}
    expected = {
        "id", "work_master_id", "name", "category", "default_unit",
        "default_labor_unit_rate", "status", "source_dataset", "source_work_id",
    }
    if set(columns) != expected or any(columns[name]["nullable"] for name in ("id", "work_master_id", "name", "status")):
        raise RuntimeError("Existing work_masters table has an incompatible column contract")
    uniques = {tuple(item["column_names"]) for item in inspector.get_unique_constraints(MASTER_TABLE)}
    if ("source_dataset", "source_work_id") not in uniques:
        raise RuntimeError("Existing work_masters table lacks its source unique constraint")
    checks = {item["name"] for item in inspector.get_check_constraints(MASTER_TABLE)}
    if "ck_work_master_source_pair" not in checks:
        raise RuntimeError("Existing work_masters table lacks its source-pair check constraint")


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "work_items" not in inspector.get_table_names():
        raise RuntimeError("Existing schema is incomplete. Run 'python -m app.core.init_db' before Alembic.")

    if MASTER_TABLE in inspector.get_table_names():
        _validate_master_table(inspector)
    else:
        status = sa.Enum(
            "VALID", "ACTIVE", "ACTIVE_WITH_WARNINGS", "NEEDS_REVIEW",
            "REJECTED", "SUPERSEDED", name="statusenum",
        )
        op.create_table(
            MASTER_TABLE,
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("work_master_id", sa.String(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("category", sa.String(), nullable=True),
            sa.Column("default_unit", sa.String(), nullable=True),
            sa.Column("default_labor_unit_rate", sa.Float(), nullable=True),
            sa.Column("status", status, nullable=False),
            sa.Column("source_dataset", sa.String(), nullable=True),
            sa.Column("source_work_id", sa.String(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("source_dataset", "source_work_id", name="uq_work_master_source"),
            sa.UniqueConstraint("work_master_id"),
            sa.CheckConstraint(
                "(source_dataset IS NULL AND source_work_id IS NULL) OR "
                "(source_dataset IS NOT NULL AND source_work_id IS NOT NULL)",
                name="ck_work_master_source_pair",
            ),
        )
        op.create_index("ix_work_masters_id", MASTER_TABLE, ["id"])
        op.create_index("ix_work_masters_work_master_id", MASTER_TABLE, ["work_master_id"], unique=True)

    inspector = sa.inspect(bind)
    work_columns = {column["name"] for column in inspector.get_columns("work_items")}
    if REF_COLUMN not in work_columns:
        with op.batch_alter_table("work_items") as batch:
            batch.add_column(sa.Column(REF_COLUMN, sa.Integer(), nullable=True))
            batch.create_foreign_key("fk_work_items_work_master_ref_id", MASTER_TABLE, [REF_COLUMN], ["id"])
            batch.create_index("ix_work_items_work_master_ref_id", [REF_COLUMN])
    else:
        fks = {tuple(fk["constrained_columns"]): fk["referred_table"] for fk in inspector.get_foreign_keys("work_items")}
        if fks.get((REF_COLUMN,)) != MASTER_TABLE:
            raise RuntimeError("Existing work_items work-master reference is incompatible")


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if "work_items" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("work_items")}
        if REF_COLUMN in columns:
            with op.batch_alter_table("work_items") as batch:
                batch.drop_index("ix_work_items_work_master_ref_id")
                batch.drop_column(REF_COLUMN)
    if MASTER_TABLE in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table(MASTER_TABLE)
