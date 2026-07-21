"""Add stable provider request idempotency keys."""

from pathlib import Path

from alembic import op

revision = "20260718_0004"
down_revision = "20260718_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    script = (Path(__file__).resolve().parents[2] / "migrations" / "009_provider_idempotency.sql").read_text()
    for statement in (part.strip() for part in script.split(";")):
        if statement:
            bind.exec_driver_sql(statement)


def downgrade() -> None:
    raise RuntimeError("Destructive schema downgrade is intentionally unsupported; restore a backup instead")
