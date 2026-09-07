"""Add the included one-way equipment delivery distance."""
from alembic import op
import sqlalchemy as sa

revision = "0002_equipment_delivery_distance"
down_revision = "0001_existing_schema"
branch_labels = None
depends_on = None
COLUMN = "included_delivery_one_way_distance_km"

def _columns():
    inspector = sa.inspect(op.get_bind())
    if "equipments" not in inspector.get_table_names():
        raise RuntimeError(
            "Equipment table is missing. Run 'python -m app.core.init_db' "
            "before 'python -m alembic upgrade head' for a fresh database."
        )
    return {column["name"] for column in inspector.get_columns("equipments")}

def upgrade():
    if COLUMN not in _columns():
        op.add_column("equipments", sa.Column(COLUMN, sa.Float(), nullable=True))

def downgrade():
    if COLUMN in _columns():
        op.drop_column("equipments", COLUMN)
