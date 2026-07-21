import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orchestra.config import Settings

settings = Settings()
print(
    {
        "environment": settings.environment,
        "database_path": settings.database_path,
        "vault_configured": bool(settings.vault_key),
        "platform_providers": sorted(settings.platform_keys),
    }
)
