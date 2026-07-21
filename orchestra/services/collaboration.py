"""Project invitations, role revocation, branch comparison, and conflict-aware merge proposals."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from orchestra.core.events import ResearchEvent
from orchestra.repositories.repository import Repository, dumps, loads, now
from orchestra.services.research import AuthorizationError, ConflictError, NotFoundError


class CollaborationService:
    def __init__(self, repository: Repository):
        self.repo = repository

    def _owner(self, actor: UUID, project_id: str) -> dict:
        project = self.repo.accessible_project(project_id, actor, True)
        if not project or project["role"] != "owner":
            raise AuthorizationError("Only the project owner can manage collaboration")
        return project

    def invite(self, actor: UUID, project_id: str, email: str, role: str) -> dict:
        self._owner(actor, project_id)
        token = secrets.token_urlsafe(32)
        invitation_id = str(uuid4())
        expires = (datetime.now(UTC) + timedelta(days=7)).isoformat()
        with self.repo.database.transaction() as connection:
            connection.execute(
                "INSERT INTO invitations VALUES(?,?,?,?,?,?,?,?,?)",
                (invitation_id, project_id, email.lower(), role, hashlib.sha256(token.encode()).hexdigest(), str(actor), "pending", expires, now()),
            )
            self.repo.append_event(
                connection,
                ResearchEvent(
                    project_id=UUID(project_id),
                    actor_id=str(actor),
                    event_type="INVITATION_CREATED",
                    payload={"invitation_id": invitation_id, "email": email.lower(), "role": role},
                ),
            )
        return {"id": invitation_id, "token": token, "role": role, "expires_at": expires}

    def accept(self, actor: UUID, token: str) -> dict:
        digest = hashlib.sha256(token.encode()).hexdigest()
        invitation = self.repo.one("SELECT i.*,u.email user_email FROM invitations i JOIN users u ON u.id=? WHERE i.token_hash=? AND i.status='pending'", (str(actor), digest))
        if not invitation or invitation["user_email"].lower() != invitation["email"] or invitation["expires_at"] < now():
            raise NotFoundError("Valid invitation not found")
        with self.repo.database.transaction() as connection:
            connection.execute(
                "INSERT INTO project_members VALUES(?,?,?,?) ON CONFLICT(project_id,user_id) DO UPDATE SET role=excluded.role,created_at=excluded.created_at",
                (invitation["project_id"], str(actor), invitation["role"], now()),
            )
            connection.execute("UPDATE invitations SET status='accepted' WHERE id=?", (invitation["id"],))
            self.repo.append_event(
                connection,
                ResearchEvent(
                    project_id=UUID(invitation["project_id"]),
                    actor_id=str(actor),
                    event_type="INVITATION_ACCEPTED",
                    payload={"invitation_id": invitation["id"], "role": invitation["role"]},
                ),
            )
        return {"project_id": invitation["project_id"], "role": invitation["role"], "status": "accepted"}

    def revoke(self, actor: UUID, project_id: str, user_id: str) -> None:
        project = self._owner(actor, project_id)
        if project["owner_id"] == user_id:
            raise ConflictError("Project ownership cannot be revoked")
        with self.repo.database.transaction() as connection:
            connection.execute("DELETE FROM project_members WHERE project_id=? AND user_id=?", (project_id, user_id))
            self.repo.append_event(connection, ResearchEvent(project_id=UUID(project_id), actor_id=str(actor), event_type="MEMBER_REVOKED", payload={"user_id": user_id}))

    def compare(self, actor: UUID, project_id: str, source_id: str, target_id: str) -> dict:
        if not self.repo.accessible_project(project_id, actor):
            raise NotFoundError("Project not found")
        source = {row["title"]: row for row in self.repo.all("SELECT id,title,kind,status,content,version FROM nodes WHERE project_id=? AND branch_id=?", (project_id, source_id))}
        target = {row["title"]: row for row in self.repo.all("SELECT id,title,kind,status,content,version FROM nodes WHERE project_id=? AND branch_id=?", (project_id, target_id))}
        added = [source[key] for key in source.keys() - target.keys()]
        removed = [target[key] for key in target.keys() - source.keys()]
        changed = [
            {"title": key, "source": source[key], "target": target[key]}
            for key in source.keys() & target.keys()
            if source[key]["content"] != target[key]["content"] or source[key]["status"] != target[key]["status"]
        ]
        return {"source_branch_id": source_id, "target_branch_id": target_id, "added": added, "removed": removed, "changed": changed, "conflicts": changed}

    def propose_merge(self, actor: UUID, project_id: str, source_id: str, target_id: str) -> dict:
        if not self.repo.accessible_project(project_id, actor, True):
            raise NotFoundError("Project not found")
        diff = self.compare(actor, project_id, source_id, target_id)
        proposal_id = str(uuid4())
        status = "conflicted" if diff["conflicts"] else "ready"
        with self.repo.database.transaction() as connection:
            connection.execute(
                "INSERT INTO merge_proposals VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (proposal_id, project_id, source_id, target_id, status, dumps(diff), dumps(diff["conflicts"]), str(actor), None, now(), now()),
            )
            self.repo.append_event(
                connection, ResearchEvent(project_id=UUID(project_id), actor_id=str(actor), event_type="MERGE_PROPOSED", payload={"proposal_id": proposal_id, "status": status})
            )
        return {"id": proposal_id, "status": status, "diff": diff}

    def resolve_merge(self, actor: UUID, proposal_id: str, resolutions: dict[str, str]) -> dict:
        proposal = self.repo.one("SELECT * FROM merge_proposals WHERE id=?", (proposal_id,))
        if not proposal or not self.repo.accessible_project(proposal["project_id"], actor, True):
            raise NotFoundError("Merge proposal not found")
        if proposal["status"] not in {"ready", "conflicted"}:
            raise ConflictError("Merge proposal is not open")
        diff = loads(proposal["diff"], {})
        conflicts = diff.get("conflicts", [])
        for conflict in conflicts:
            if resolutions.get(conflict["title"]) not in {"source", "target"}:
                raise ConflictError(f"Resolution required for {conflict['title']}")
        target_branch = proposal["target_branch_id"]
        source_nodes = self.repo.all("SELECT * FROM nodes WHERE project_id=? AND branch_id=?", (proposal["project_id"], proposal["source_branch_id"]))
        target_nodes = self.repo.all("SELECT * FROM nodes WHERE project_id=? AND branch_id=?", (proposal["project_id"], target_branch))
        target_by_title = {node["title"]: node["id"] for node in target_nodes}
        node_map: dict[str, str] = {node["id"]: target_by_title[node["title"]] for node in source_nodes if node["title"] in target_by_title}
        claim_map: dict[str, str] = {}
        with self.repo.database.transaction() as connection:
            for node in diff.get("added", []):
                new_id = str(uuid4())
                node_map[node["id"]] = new_id
                full = connection.execute("SELECT * FROM nodes WHERE id=?", (node["id"],)).fetchone()
                connection.execute(
                    "INSERT INTO nodes VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        new_id,
                        full["project_id"],
                        target_branch,
                        full["run_id"],
                        full["kind"],
                        full["title"],
                        full["content"],
                        full["status"],
                        full["position"],
                        full["provenance"],
                        full["version"],
                        full["created_at"],
                        now(),
                    ),
                )
                source_claim = connection.execute("SELECT * FROM claims WHERE node_id=?", (node["id"],)).fetchone()
                if source_claim:
                    new_claim_id = str(uuid4())
                    claim_map[source_claim["id"]] = new_claim_id
                    connection.execute(
                        "INSERT INTO claims VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                        (new_claim_id, source_claim["project_id"], new_id, source_claim["statement"], source_claim["latex"], source_claim["assumptions"], source_claim["status"], source_claim["confidence"], source_claim["proposed_by"], source_claim["required_capabilities"], source_claim["created_at"], now()),
                    )
            for source_node_id, target_node_id in node_map.items():
                source_claim = connection.execute("SELECT id FROM claims WHERE node_id=?", (source_node_id,)).fetchone()
                target_claim = connection.execute("SELECT id FROM claims WHERE node_id=?", (target_node_id,)).fetchone()
                if source_claim and target_claim:
                    claim_map[source_claim["id"]] = target_claim["id"]
            for node in diff.get("added", []):
                source_evidence = connection.execute("SELECT * FROM evidence WHERE node_id=?", (node["id"],)).fetchone()
                if source_evidence and source_evidence["claim_id"] in claim_map:
                    connection.execute(
                        "INSERT INTO evidence VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (str(uuid4()), source_evidence["project_id"], node_map[node["id"]], claim_map[source_evidence["claim_id"]], source_evidence["evidence_type"], source_evidence["stance"], source_evidence["title"], source_evidence["content"], source_evidence["source"], source_evidence["reliability"], source_evidence["reproducibility"], source_evidence["assumptions"], source_evidence["independence_group"], source_evidence["immutable_hash"], source_evidence["created_at"]),
                    )
            source_edges = connection.execute("SELECT * FROM edges WHERE project_id=? AND branch_id=?", (proposal["project_id"], proposal["source_branch_id"])).fetchall()
            for edge in source_edges:
                if edge["source_id"] in node_map and edge["target_id"] in node_map:
                    connection.execute(
                        "INSERT INTO edges VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(project_id,source_id,target_id,edge_type) DO NOTHING",
                        (str(uuid4()), proposal["project_id"], target_branch, node_map[edge["source_id"]], node_map[edge["target_id"]], edge["edge_type"], edge["metadata"], now()),
                    )
            for conflict in conflicts:
                if resolutions[conflict["title"]] == "source":
                    source = conflict["source"]
                    connection.execute(
                        "UPDATE nodes SET content=?,status=?,version=version+1,updated_at=? WHERE id=?", (source["content"], source["status"], now(), conflict["target"]["id"])
                    )
                    source_claim = connection.execute("SELECT * FROM claims WHERE node_id=?", (source["id"],)).fetchone()
                    if source_claim:
                        connection.execute(
                            "UPDATE claims SET statement=?,latex=?,assumptions=?,status=?,confidence=?,required_capabilities=?,updated_at=? WHERE node_id=?",
                            (source_claim["statement"], source_claim["latex"], source_claim["assumptions"], source_claim["status"], source_claim["confidence"], source_claim["required_capabilities"], now(), conflict["target"]["id"]),
                        )
            connection.execute("UPDATE merge_proposals SET status='merged',reviewed_by=?,updated_at=? WHERE id=?", (str(actor), now(), proposal_id))
            self.repo.append_event(
                connection,
                ResearchEvent(
                    project_id=UUID(proposal["project_id"]),
                    actor_id=str(actor),
                    event_type="MERGE_COMPLETED",
                    payload={"proposal_id": proposal_id, "resolutions": resolutions, "added_node_ids": list(node_map.values())},
                ),
            )
        return {"id": proposal_id, "status": "merged", "added_node_ids": list(node_map.values())}
