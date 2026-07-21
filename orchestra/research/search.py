from __future__ import annotations

from uuid import UUID, uuid4

from orchestra.repositories.repository import Repository, dumps, loads, now
from orchestra.research.embeddings import HashEmbedding


class SemanticSearch:
    def __init__(self, repository: Repository):
        self.repo = repository
        self.embedding = HashEmbedding()

    def search(self, actor: UUID, query: str, project_id: str | None = None, limit: int = 20) -> list[dict]:
        accessible = self.repo.all(
            "SELECT DISTINCT p.id FROM projects p LEFT JOIN project_members pm ON pm.project_id=p.id AND pm.user_id=? WHERE p.owner_id=? OR pm.user_id=? OR p.visibility='public'",
            (str(actor), str(actor), str(actor)),
        )
        project_ids = {row["id"] for row in accessible}
        if project_id:
            project_ids &= {project_id}
        query_vector = self.embedding.encode(query)
        candidates = []
        for pid in project_ids:
            for node in self.repo.all("SELECT id,project_id,kind,title,content,status FROM nodes WHERE project_id=?", (pid,)):
                text = node["title"] + " " + node["content"]
                vector = self._persist(pid, "node", node["id"], text)
                candidates.append(
                    {
                        "object_type": "node",
                        "object_id": node["id"],
                        "project_id": pid,
                        "title": node["title"],
                        "kind": node["kind"],
                        "status": node["status"],
                        "similarity": self.embedding.similarity(query_vector, vector),
                    }
                )
        return sorted(candidates, key=lambda item: item["similarity"], reverse=True)[: min(limit, 100)]

    def _persist(self, project_id: str, object_type: str, object_id: str, text: str) -> list[float]:
        existing = self.repo.one("SELECT vector,search_text FROM embeddings WHERE object_type=? AND object_id=? AND model=?", (object_type, object_id, self.embedding.model))
        if existing and existing["search_text"] == text:
            return loads(existing["vector"], [])
        vector = self.embedding.encode(text)
        self.repo.execute(
            "INSERT INTO embeddings VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(object_type,object_id,model) DO UPDATE SET vector=excluded.vector,search_text=excluded.search_text,created_at=excluded.created_at",
            (str(uuid4()), project_id, object_type, object_id, self.embedding.model, self.embedding.dimensions, dumps(vector), text, now()),
        )
        return vector
