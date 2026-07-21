import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orchestra.config import settings
from orchestra.storage.db import Database

Database(settings.database_url or settings.database_path).migrate()
print("Database migrations applied")
