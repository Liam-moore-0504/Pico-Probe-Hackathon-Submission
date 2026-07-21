"""Content-addressed local artifact storage with strict upload policy."""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from uuid import UUID, uuid4

from orchestra.core.events import ResearchEvent
from orchestra.repositories.repository import Repository, dumps, now

ALLOWED_TYPES = {"application/json", "text/plain", "text/csv", "application/pdf", "image/png", "image/jpeg"}


class ArtifactStore:
    def __init__(self, repository: Repository, root: str = "orchestra_artifacts", maximum_bytes: int = 20 * 1024 * 1024):
        self.repo = repository
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.maximum_bytes = maximum_bytes

    def store(self, actor: UUID, project_id: str, filename: str, media_type: str, content: bytes, run_id: str | None = None) -> dict:
        if media_type not in ALLOWED_TYPES:
            raise ValueError("Unsupported artifact content type")
        if not content or len(content) > self.maximum_bytes:
            raise ValueError(f"Artifact must contain 1 to {self.maximum_bytes} bytes")
        safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", Path(filename).name)[:180]
        digest = hashlib.sha256(content).hexdigest()
        key = f"{project_id}/{digest[:2]}/{digest}_{safe_name}"
        destination = (self.root / key).resolve()
        if self.root not in destination.parents:
            raise ValueError("Invalid artifact path")
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.write_bytes(content)
        os.replace(temporary, destination)
        artifact_id = str(uuid4())
        with self.repo.database.transaction() as connection:
            connection.execute(
                "INSERT INTO artifacts VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (artifact_id, project_id, run_id, str(actor), safe_name, media_type, len(content), digest, key, dumps({}), now()),
            )
            self.repo.append_event(
                connection,
                ResearchEvent(
                    project_id=UUID(project_id),
                    run_id=UUID(run_id) if run_id else None,
                    actor_id=str(actor),
                    event_type="ARTIFACT_STORED",
                    payload={"artifact_id": artifact_id, "filename": safe_name, "sha256": digest, "size_bytes": len(content)},
                ),
            )
        return {"id": artifact_id, "filename": safe_name, "media_type": media_type, "size_bytes": len(content), "sha256": digest, "created_at": now()}

    def path(self, storage_key: str) -> Path:
        candidate = (self.root / storage_key).resolve()
        if self.root not in candidate.parents or not candidate.is_file():
            raise FileNotFoundError
        return candidate
