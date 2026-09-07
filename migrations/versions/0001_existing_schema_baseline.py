"""Baseline for databases initialized before Alembic."""
from alembic import op
import sqlalchemy as sa

revision = "0001_existing_schema"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    required = {
        "projects", "work_items", "materials", "work_material_links",
        "equipments", "transports",
    }
    present = set(sa.inspect(op.get_bind()).get_table_names())
    missing = sorted(required - present)
    if missing:
        raise RuntimeError(
            "Existing schema is incomplete (missing: " + ", ".join(missing)
            + "). Run 'python -m app.core.init_db' before Alembic for a fresh database."
        )

def downgrade():
    pass
