"""Compiled research protocol, canonical messages, and Ollama settings."""

from pathlib import Path

from alembic import op

revision = "20260720_0005"
down_revision = "20260718_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    root = Path(__file__).resolve().parents[2]
    for name in ("010_research_compilation.sql", "011_pipeline_messages_ollama.sql"):
        script = (root / "migrations" / name).read_text()
        for statement in (part.strip() for part in script.split(";")):
            if statement:
                bind.exec_driver_sql(statement)


def downgrade() -> None:
    raise RuntimeError("Destructive schema downgrade is intentionally unsupported; restore a backup instead")
