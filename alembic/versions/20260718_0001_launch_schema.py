"""Create the complete Pico Probe launch schema."""

from pathlib import Path

from alembic import op

revision = "20260718_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    postgres = bind.dialect.name == "postgresql"
    root = Path(__file__).resolve().parents[2]
    for name in ("001_initial.sql", "002_indexes.sql", "003_launch_subsystems.sql", "004_account_security.sql"):
        migration = root / "migrations" / name
        script = migration.read_text()
        if postgres:
            script = script.replace("PRAGMA foreign_keys=ON;", "")
        for statement in (part.strip() for part in script.split(";")):
            if statement:
                bind.exec_driver_sql(statement)


def downgrade() -> None:
    raise RuntimeError("Destructive launch-schema downgrade is intentionally unsupported; restore a backup instead")
