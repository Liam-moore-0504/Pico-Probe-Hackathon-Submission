"""Provider execution, signed plugins, and security audit."""

from pathlib import Path

from alembic import op

revision = "20260718_0002"
down_revision = "20260718_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    root = Path(__file__).resolve().parents[2]
    for name in ("005_provider_execution.sql", "006_signed_plugins.sql", "007_security_audit.sql"):
        script = (root / "migrations" / name).read_text()
        for statement in (part.strip() for part in script.split(";")):
            if statement:
                bind.exec_driver_sql(statement)


def downgrade() -> None:
    raise RuntimeError("Destructive schema downgrade is intentionally unsupported; restore a backup instead")
