"""Transactional application service for the persistent Research Graph."""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from orchestra.auth.security import decode_token, hash_password, issue_tokens, verify_password
from orchestra.core.confidence import Signal, calculate_with_explanation
from orchestra.core.enums import ClaimStatus, EdgeType, ProjectRole
from orchestra.core.events import ResearchEvent
from orchestra.core.graph import GraphCycleError, ResearchGraph
from orchestra.core.lifecycle import transition
from orchestra.core.models import ResearchEdge, ResearchNode
from orchestra.demo import bundled_public_projects, bundled_public_snapshot
from orchestra.repositories import Repository
from orchestra.repositories.repository import dumps, loads, now
from orchestra.research.similarity import TokenOverlapSimilarity, fingerprint, normalize
from orchestra.storage.vault import SecretBackend

try:
    import psycopg

    INTEGRITY_ERRORS = (sqlite3.IntegrityError, psycopg.IntegrityError)
except ImportError:  # pragma: no cover - PostgreSQL dependency is optional in minimal development environments
    INTEGRITY_ERRORS = (sqlite3.IntegrityError,)


class NotFoundError(ValueError):
    pass


class AuthorizationError(PermissionError):
    pass


class ConflictError(ValueError):
    pass


class ValidationError(ValueError):
    pass


class InsufficientCreditsError(ValueError):
    pass


def uid(prefix: str = "") -> str:
    return prefix + uuid4().hex


class ResearchService:
    """Enforces domain rules and performs each graph mutation atomically."""

    def __init__(self, repository: Repository, vault: SecretBackend, jwt_secret: str | None = None):
        self.repo = repository
        self.vault = vault
        self.jwt_secret = jwt_secret
        self.similarity = TokenOverlapSimilarity()
        self.plugin_registry = None
        self.provider_metadata: dict[str, dict] = {}
        self.platform_keys: dict[str, str] = {}

    def configure_execution(self, plugin_registry, provider_metadata: dict[str, dict], platform_keys: dict[str, str]) -> None:
        self.plugin_registry = plugin_registry
        self.provider_metadata = provider_metadata
        self.platform_keys = platform_keys

    def register(self, username: str, email: str, password: str, is_admin: bool = False) -> dict:
        user_id = str(uuid4())
        try:
            with self.repo.database.transaction() as connection:
                connection.execute(
                    "INSERT INTO users(id,username,email,password_hash,email_verified,created_at,token_version,is_admin) VALUES(?,?,?,?,?,?,0,?)",
                    (user_id, username, email.lower(), hash_password(password), 0, now(), int(is_admin)),
                )
        except INTEGRITY_ERRORS as exc:
            raise ConflictError("Username or email already exists") from exc
        self._security_audit(user_id, "account_registered", None, {})
        return {"user_id": user_id, "status": "registered"}

    def login(self, username: str, password: str, remote: str = "unknown") -> dict:
        since = (datetime.now(UTC) - timedelta(minutes=15)).isoformat()
        failures = self.repo.one(
            "SELECT COUNT(*) count FROM login_attempts WHERE username=? AND remote_hash=? AND succeeded=0 AND created_at>=?",
            (username, hashlib.sha256(remote.encode()).hexdigest(), since),
        )
        if failures and failures["count"] >= 10:
            raise AuthorizationError("Too many login attempts; try again later")
        row = self.repo.one("SELECT * FROM users WHERE username=?", (username,))
        succeeded = bool(row and verify_password(password, row["password_hash"]))
        self.repo.execute("INSERT INTO login_attempts VALUES(?,?,?,?,?)", (str(uuid4()), username, hashlib.sha256(remote.encode()).hexdigest(), int(succeeded), now()))
        if not succeeded:
            self._security_audit(row["id"] if row else None, "login_failed", remote, {"username_hash": hashlib.sha256(username.encode()).hexdigest()})
            raise AuthorizationError("Invalid credentials")
        self._security_audit(row["id"], "login_succeeded", remote, {})
        return issue_tokens(row["id"], row.get("token_version", 0) if isinstance(row, dict) else row["token_version"], self.jwt_secret)

    def refresh(self, refresh_token: str) -> dict:
        payload = decode_token(refresh_token, "refresh", self.jwt_secret)
        if not payload or self.repo.one("SELECT 1 FROM revoked_tokens WHERE jti=?", (payload.get("jti"),)):
            raise AuthorizationError("Invalid or expired refresh token")
        with self.repo.database.transaction() as connection:
            connection.execute("INSERT INTO revoked_tokens VALUES(?,?)", (payload["jti"], datetime.fromtimestamp(payload["exp"], UTC).isoformat()))
        user = self.repo.one("SELECT token_version FROM users WHERE id=?", (payload["sub"],))
        if not user or user["token_version"] != payload.get("ver", 0):
            raise AuthorizationError("Refresh token has been revoked")
        return issue_tokens(payload["sub"], user["token_version"], self.jwt_secret)

    def create_project(self, actor: UUID, data: dict) -> dict:
        project_id, branch_id, timestamp = str(uuid4()), str(uuid4()), now()
        with self.repo.database.transaction() as connection:
            connection.execute(
                "INSERT INTO projects VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    project_id,
                    str(actor),
                    data["title"],
                    data["question"],
                    data.get("abstract", ""),
                    "private",
                    "active",
                    dumps(data.get("tags", [])),
                    timestamp,
                    timestamp,
                ),
            )
            connection.execute("INSERT INTO project_members VALUES(?,?,?,?)", (project_id, str(actor), ProjectRole.OWNER.value, timestamp))
            connection.execute("INSERT INTO branches VALUES(?,?,?,?,?,?,?)", (branch_id, project_id, "main", None, None, str(actor), timestamp))
            self.repo.append_event(
                connection,
                ResearchEvent(
                    project_id=UUID(project_id),
                    branch_id=UUID(branch_id),
                    actor_id=str(actor),
                    event_type="PROJECT_CREATED",
                    payload={"title": data["title"], "question": data["question"]},
                ),
            )
            self.repo.append_event(
                connection,
                ResearchEvent(
                    project_id=UUID(project_id), branch_id=UUID(branch_id), actor_id=str(actor), event_type="BRANCH_CREATED", payload={"branch_id": branch_id, "name": "main"}
                ),
            )
        return self.get_project(actor, project_id)

    def _project(self, actor: UUID, project_id: str, write: bool = False) -> dict:
        project = self.repo.accessible_project(project_id, actor, write)
        if not project:
            raise NotFoundError("Project not found")
        project["tags"] = loads(project.get("tags"), [])
        return project

    def get_project(self, actor: UUID, project_id: str) -> dict:
        return self._project(actor, project_id)

    def list_projects(self, actor: UUID) -> list[dict]:
        rows = self.repo.all(
            """SELECT DISTINCT p.*, CASE WHEN p.owner_id=? THEN 'owner' ELSE pm.role END role
            FROM projects p LEFT JOIN project_members pm ON p.id=pm.project_id WHERE p.owner_id=? OR pm.user_id=? ORDER BY p.updated_at DESC""",
            (str(actor), str(actor), str(actor)),
        )
        for row in rows:
            row["tags"] = loads(row["tags"], [])
        return rows

    def add_member(self, actor: UUID, project_id: str, user_id: str, role: str) -> dict:
        project = self._project(actor, project_id, True)
        if project["role"] != "owner":
            raise AuthorizationError("Only owners can manage members")
        if role == "owner":
            raise ValidationError("Ownership transfer is a separate operation")
        with self.repo.database.transaction() as connection:
            connection.execute(
                "INSERT INTO project_members VALUES(?,?,?,?) ON CONFLICT(project_id,user_id) DO UPDATE SET role=excluded.role,created_at=excluded.created_at",
                (project_id, user_id, role, now()),
            )
            self.repo.append_event(
                connection, ResearchEvent(project_id=UUID(project_id), actor_id=str(actor), event_type="MEMBER_ADDED", payload={"user_id": user_id, "role": role})
            )
        return {"user_id": user_id, "role": role}

    def create_branch(self, actor: UUID, project_id: str, name: str, parent_id: str | None) -> dict:
        self._project(actor, project_id, True)
        branch_id = str(uuid4())
        parent = parent_id or self.repo.one("SELECT id FROM branches WHERE project_id=? AND name='main'", (project_id,))["id"]
        source_nodes = self.repo.all("SELECT * FROM nodes WHERE project_id=? AND branch_id=?", (project_id, parent))
        source_edges = self.repo.all("SELECT * FROM edges WHERE project_id=? AND branch_id=?", (project_id, parent))
        node_map = {node["id"]: str(uuid4()) for node in source_nodes}
        claim_map: dict[str, str] = {}
        with self.repo.database.transaction() as connection:
            connection.execute("INSERT INTO branches VALUES(?,?,?,?,?,?,?)", (branch_id, project_id, name, parent, None, str(actor), now()))
            for node in source_nodes:
                connection.execute(
                    "INSERT INTO nodes VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        node_map[node["id"]],
                        project_id,
                        branch_id,
                        node["run_id"],
                        node["kind"],
                        node["title"],
                        node["content"],
                        node["status"],
                        node["position"],
                        node["provenance"],
                        node["version"],
                        node["created_at"],
                        node["updated_at"],
                    ),
                )
            source_claims = connection.execute("SELECT * FROM claims WHERE project_id=?", (project_id,)).fetchall()
            for claim in source_claims:
                if claim["node_id"] not in node_map:
                    continue
                new_claim_id = str(uuid4())
                claim_map[claim["id"]] = new_claim_id
                connection.execute(
                    "INSERT INTO claims VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (new_claim_id, project_id, node_map[claim["node_id"]], claim["statement"], claim["latex"], claim["assumptions"], claim["status"], claim["confidence"], claim["proposed_by"], claim["required_capabilities"], claim["created_at"], claim["updated_at"]),
                )
            source_evidence = connection.execute("SELECT * FROM evidence WHERE project_id=?", (project_id,)).fetchall()
            for evidence in source_evidence:
                if evidence["node_id"] not in node_map or evidence["claim_id"] not in claim_map:
                    continue
                connection.execute(
                    "INSERT INTO evidence VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (str(uuid4()), project_id, node_map[evidence["node_id"]], claim_map[evidence["claim_id"]], evidence["evidence_type"], evidence["stance"], evidence["title"], evidence["content"], evidence["source"], evidence["reliability"], evidence["reproducibility"], evidence["assumptions"], evidence["independence_group"], evidence["immutable_hash"], evidence["created_at"]),
                )
            for review in connection.execute("SELECT * FROM reviews WHERE project_id=?", (project_id,)).fetchall():
                if review["claim_id"] in claim_map:
                    connection.execute(
                        "INSERT INTO reviews VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (str(uuid4()), project_id, claim_map[review["claim_id"]], review["actor"], review["stance"], review["reason"], review["assumptions"], review["confidence"], review["independence_group"], review["created_at"]),
                    )
            for dead_end in connection.execute("SELECT * FROM dead_ends WHERE project_id=? AND branch_id=?", (project_id, parent)).fetchall():
                if dead_end["node_id"] in node_map:
                    connection.execute(
                        "INSERT INTO dead_ends VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (str(uuid4()), project_id, branch_id, dead_end["run_id"], node_map[dead_end["node_id"]], claim_map.get(dead_end["target_id"], dead_end["target_id"]), dead_end["approach"], dead_end["normalized_strategy"], dead_end["assumptions"], dead_end["method"], dead_end["failure"], dead_end["lesson"], dead_end["applies_where"], dead_end["may_not_apply_where"], dead_end["discovered_by"], dead_end["fingerprint"], dead_end["search_text"], dead_end["created_at"]),
                    )
            for edge in source_edges:
                if edge["source_id"] in node_map and edge["target_id"] in node_map:
                    connection.execute(
                        "INSERT INTO edges VALUES(?,?,?,?,?,?,?,?)",
                        (str(uuid4()), project_id, branch_id, node_map[edge["source_id"]], node_map[edge["target_id"]], edge["edge_type"], edge["metadata"], edge["created_at"]),
                    )
            self.repo.append_event(
                connection,
                ResearchEvent(
                    project_id=UUID(project_id),
                    branch_id=UUID(branch_id),
                    actor_id=str(actor),
                    event_type="BRANCH_CREATED",
                    payload={"branch_id": branch_id, "name": name, "parent_id": parent},
                ),
            )
        return {"id": branch_id, "project_id": project_id, "name": name, "parent_id": parent}

    def graph(self, actor: UUID, project_id: str, branch_id: str | None = None) -> dict:
        self._project(actor, project_id)
        if branch_id:
            nodes = self.repo.all("SELECT * FROM nodes WHERE project_id=? AND branch_id=?", (project_id, branch_id))
            edges = self.repo.all("SELECT * FROM edges WHERE project_id=? AND branch_id=?", (project_id, branch_id))
        else:
            nodes = self.repo.all("SELECT * FROM nodes WHERE project_id=?", (project_id,))
            edges = self.repo.all("SELECT * FROM edges WHERE project_id=?", (project_id,))
        for node in nodes:
            for key in ("content", "position", "provenance"):
                node[key] = loads(node[key], {})
        for edge in edges:
            edge["metadata"] = loads(edge["metadata"], {})
        return {"nodes": nodes, "edges": edges}

    def create_node(self, actor: UUID, project_id: str, data: dict) -> dict:
        self._project(actor, project_id, True)
        node_id, timestamp = str(uuid4()), now()
        with self.repo.database.transaction() as connection:
            connection.execute(
                "INSERT INTO nodes VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    node_id,
                    project_id,
                    data.get("branch_id"),
                    data.get("run_id"),
                    data["kind"],
                    data["title"],
                    dumps(data.get("content", {})),
                    data.get("status", "pending"),
                    dumps(data.get("position", {"x": 0, "y": 0})),
                    dumps(data.get("provenance", {"actor": str(actor)})),
                    1,
                    timestamp,
                    timestamp,
                ),
            )
            self.repo.append_event(
                connection, ResearchEvent(project_id=UUID(project_id), actor_id=str(actor), event_type="RESEARCH_NODE_CREATED", payload={"node_id": node_id, "kind": data["kind"]})
            )
        return self.repo.one("SELECT * FROM nodes WHERE id=?", (node_id,))

    def patch_node(self, actor: UUID, project_id: str, node_id: str, data: dict) -> dict:
        self._project(actor, project_id, True)
        node = self.repo.one("SELECT * FROM nodes WHERE id=? AND project_id=?", (node_id, project_id))
        if not node:
            raise NotFoundError("Node not found")
        title, status = data.get("title", node["title"]), data.get("status", node["status"])
        content = data.get("content", loads(node["content"], {}))
        position = data.get("position", loads(node["position"], {}))
        with self.repo.database.transaction() as connection:
            connection.execute(
                "UPDATE nodes SET title=?,status=?,content=?,position=?,version=version+1,updated_at=? WHERE id=?", (title, status, dumps(content), dumps(position), now(), node_id)
            )
            self.repo.append_event(
                connection,
                ResearchEvent(project_id=UUID(project_id), actor_id=str(actor), event_type="RESEARCH_NODE_UPDATED", payload={"node_id": node_id, "fields": sorted(data)}),
            )
        return self.repo.one("SELECT * FROM nodes WHERE id=?", (node_id,))

    def delete_graph_object(self, actor: UUID, project_id: str, object_id: str, kind: str) -> None:
        self._project(actor, project_id, True)
        query = "SELECT id FROM nodes WHERE id=? AND project_id=?" if kind == "node" else "SELECT id FROM edges WHERE id=? AND project_id=?"
        row = self.repo.one(query, (object_id, project_id))
        if not row:
            raise NotFoundError(f"Graph {kind} not found")
        event_type = "RESEARCH_NODE_DELETED" if kind == "node" else "RESEARCH_EDGE_DELETED"
        with self.repo.database.transaction() as connection:
            delete_query = "DELETE FROM nodes WHERE id=?" if kind == "node" else "DELETE FROM edges WHERE id=?"
            connection.execute(delete_query, (object_id,))
            self.repo.append_event(connection, ResearchEvent(project_id=UUID(project_id), actor_id=str(actor), event_type=event_type, payload={f"{kind}_id": object_id}))

    def _assert_dag(self, project_id: str, source: str, target: str) -> None:
        graph = ResearchGraph()
        for row in self.repo.all("SELECT id,kind,title FROM nodes WHERE project_id=?", (project_id,)):
            graph.add_node(ResearchNode(id=UUID(row["id"]), kind=row["kind"], title=row["title"]))
        for row in self.repo.all("SELECT id,source_id,target_id,edge_type FROM edges WHERE project_id=?", (project_id,)):
            graph.add_edge(ResearchEdge(id=UUID(row["id"]), source_id=UUID(row["source_id"]), target_id=UUID(row["target_id"]), edge_type=row["edge_type"]))
        graph.add_edge(ResearchEdge(source_id=UUID(source), target_id=UUID(target), edge_type=EdgeType.DEPENDS_ON))

    def create_edge(self, actor: UUID, project_id: str, data: dict) -> dict:
        self._project(actor, project_id, True)
        try:
            self._assert_dag(project_id, data["source_id"], data["target_id"])
        except (GraphCycleError, ValueError) as exc:
            raise ValidationError(str(exc)) from exc
        edge_id = str(uuid4())
        with self.repo.database.transaction() as connection:
            connection.execute(
                "INSERT INTO edges VALUES(?,?,?,?,?,?,?,?)",
                (
                    edge_id,
                    project_id,
                    data.get("branch_id"),
                    data["source_id"],
                    data["target_id"],
                    data["edge_type"],
                    dumps(data.get("metadata", {})),
                    now(),
                ),
            )
            self.repo.append_event(
                connection, ResearchEvent(project_id=UUID(project_id), actor_id=str(actor), event_type="RESEARCH_EDGE_CREATED", payload={"edge_id": edge_id, **data})
            )
        return self.repo.one("SELECT * FROM edges WHERE id=?", (edge_id,))

    def create_claim(self, actor: UUID, project_id: str, data: dict) -> dict:
        self._project(actor, project_id, True)
        claim_id, node_id, timestamp = str(uuid4()), str(uuid4()), now()
        branch = data.get("branch_id") or self.repo.one("SELECT id FROM branches WHERE project_id=? AND name='main'", (project_id,))["id"]
        with self.repo.database.transaction() as connection:
            connection.execute(
                "INSERT INTO nodes VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    node_id,
                    project_id,
                    branch,
                    data.get("run_id"),
                    "claim",
                    data["statement"],
                    dumps(data),
                    "proposed",
                    dumps({"x": 0, "y": 0}),
                    dumps({"actor": str(actor), "mode": data.get("execution_mode", "local")}),
                    1,
                    timestamp,
                    timestamp,
                ),
            )
            connection.execute(
                "INSERT INTO claims VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    claim_id,
                    project_id,
                    node_id,
                    data["statement"],
                    data.get("latex"),
                    dumps(data.get("assumptions", [])),
                    "proposed",
                    0.2,
                    data.get("proposed_by", str(actor)),
                    dumps(data.get("required_capabilities", [])),
                    timestamp,
                    timestamp,
                ),
            )
            self.repo.append_event(
                connection,
                ResearchEvent(
                    project_id=UUID(project_id), branch_id=UUID(branch), actor_id=str(actor), event_type="RESEARCH_NODE_CREATED", payload={"node_id": node_id, "kind": "claim"}
                ),
            )
            self.repo.append_event(
                connection,
                ResearchEvent(
                    project_id=UUID(project_id),
                    branch_id=UUID(branch),
                    actor_id=str(actor),
                    event_type="CLAIM_PROPOSED",
                    payload={"claim_id": claim_id, "node_id": node_id, "statement": data["statement"]},
                ),
            )
        return self.claim(actor, project_id, claim_id)

    def claim(self, actor: UUID, project_id: str, claim_id: str) -> dict:
        self._project(actor, project_id)
        row = self.repo.one("SELECT * FROM claims WHERE id=? AND project_id=?", (claim_id, project_id))
        if not row:
            raise NotFoundError("Claim not found")
        row["assumptions"] = loads(row["assumptions"], [])
        row["required_capabilities"] = loads(row["required_capabilities"], [])
        return row

    def _claim_facts(self, claim_id: str) -> dict:
        evidence = self.repo.all("SELECT stance,evidence_type,source,independence_group FROM evidence WHERE claim_id=?", (claim_id,))
        groups = {x["independence_group"] or x["source"] for x in evidence if x["stance"] == "supports"}
        return {
            "supporting_evidence": any(x["stance"] == "supports" for x in evidence),
            "independent_sources": len(groups),
            "formal_verification": any(x["evidence_type"] == "formal_verification" and x["stance"] == "supports" for x in evidence),
            "counterexample": any(x["evidence_type"] == "counterexample" for x in evidence),
            "falsification": any(x["stance"] == "contradicts" and x["evidence_type"] in {"counterexample", "formal_falsification", "human_decision"} for x in evidence),
        }

    def transition_claim(self, actor: UUID, project_id: str, claim_id: str, target: ClaimStatus) -> dict:
        self._project(actor, project_id, True)
        claim = self.claim(actor, project_id, claim_id)
        new = transition(ClaimStatus(claim["status"]), target, self._claim_facts(claim_id))
        with self.repo.database.transaction() as connection:
            connection.execute("UPDATE claims SET status=?,updated_at=? WHERE id=?", (new.value, now(), claim_id))
            connection.execute("UPDATE nodes SET status=?,updated_at=? WHERE id=?", (new.value, now(), claim["node_id"]))
            self.repo.append_event(
                connection,
                ResearchEvent(
                    project_id=UUID(project_id),
                    actor_id=str(actor),
                    event_type="CLAIM_STATUS_CHANGED",
                    payload={"claim_id": claim_id, "previous": claim["status"], "status": new.value},
                ),
            )
        if new in {ClaimStatus.DISPROVEN, ClaimStatus.INVALIDATED}:
            self.invalidate_descendants(actor, project_id, claim["node_id"])
        return self.claim(actor, project_id, claim_id)

    def attach_evidence(self, actor: UUID, project_id: str, claim_id: str, data: dict, stance: str = "supports") -> dict:
        self._project(actor, project_id, True)
        claim = self.claim(actor, project_id, claim_id)
        evidence_id, node_id, edge_id, timestamp = str(uuid4()), str(uuid4()), str(uuid4()), now()
        evidence_type = data.get("evidence_type", "observation")
        if evidence_type == "formal_verification":
            verification = data.get("content", {})
            if not (verification.get("formal") is True and verification.get("verified") is True and verification.get("verification_status") == "compiler_verified"):
                raise ValidationError("Formal-verification evidence requires a compiler-verified formal result")
        if stance == "counterexample":
            evidence_type, stance = "counterexample", "contradicts"
        material = dumps({**data, "claim_id": claim_id, "stance": stance})
        immutable_hash = hashlib.sha256(material.encode()).hexdigest()
        kind = "counterexample" if evidence_type == "counterexample" else "contradiction" if stance == "contradicts" else "evidence"
        relation = "disproves" if kind == "counterexample" else "contradicts" if stance == "contradicts" else "supports"
        branch = self.repo.one("SELECT branch_id FROM nodes WHERE id=?", (claim["node_id"],))["branch_id"]
        with self.repo.database.transaction() as connection:
            connection.execute(
                "INSERT INTO nodes VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    node_id,
                    project_id,
                    branch,
                    data.get("run_id"),
                    kind,
                    data["title"],
                    dumps(data.get("content", {})),
                    "completed",
                    dumps({"x": 0, "y": 0}),
                    dumps({"source": data.get("source", str(actor)), "immutable_hash": immutable_hash, "mode": data.get("execution_mode", "local")}),
                    1,
                    timestamp,
                    timestamp,
                ),
            )
            connection.execute(
                "INSERT INTO evidence VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    evidence_id,
                    project_id,
                    node_id,
                    claim_id,
                    evidence_type,
                    stance,
                    data["title"],
                    dumps(data.get("content", {})),
                    data.get("source", str(actor)),
                    data.get("reliability", 0.5),
                    dumps(data.get("reproducibility", {})),
                    dumps(data.get("assumptions", [])),
                    data.get("independence_group"),
                    immutable_hash,
                    timestamp,
                ),
            )
            connection.execute("INSERT INTO edges VALUES(?,?,?,?,?,?,?,?)", (edge_id, project_id, branch, node_id, claim["node_id"], relation, dumps({}), timestamp))
            event_type = "COUNTEREXAMPLE_FOUND" if kind == "counterexample" else "CONTRADICTION_ATTACHED" if stance == "contradicts" else "EVIDENCE_ATTACHED"
            self.repo.append_event(
                connection,
                ResearchEvent(
                    project_id=UUID(project_id),
                    actor_id=str(actor),
                    event_type=event_type,
                    payload={"claim_id": claim_id, "evidence_id": evidence_id, "node_id": node_id, "immutable_hash": immutable_hash},
                ),
            )
        self.recalculate_confidence(project_id, claim_id)
        if kind == "counterexample":
            current = ClaimStatus(claim["status"])
            if current in {
                ClaimStatus.PROPOSED,
                ClaimStatus.UNDER_TEST,
                ClaimStatus.TESTED,
                ClaimStatus.SUPPORTED,
                ClaimStatus.INDEPENDENTLY_CONFIRMED,
                ClaimStatus.FORMALLY_VERIFIED,
            }:
                # Normalize early states through under-test so the guarded state remains auditable.
                with self.repo.database.transaction() as connection:
                    connection.execute("UPDATE claims SET status='counterexample_found',updated_at=? WHERE id=?", (now(), claim_id))
                    connection.execute("UPDATE nodes SET status='counterexample_found',updated_at=? WHERE id=?", (now(), claim["node_id"]))
                    self.repo.append_event(
                        connection,
                        ResearchEvent(
                            project_id=UUID(project_id),
                            actor_id=str(actor),
                            event_type="CLAIM_STATUS_CHANGED",
                            payload={"claim_id": claim_id, "previous": current.value, "status": "counterexample_found", "reason": "linked counterexample"},
                        ),
                    )
        return self.repo.one("SELECT * FROM evidence WHERE id=?", (evidence_id,))

    def add_review(self, actor: UUID, project_id: str, claim_id: str, data: dict) -> dict:
        self._project(actor, project_id)
        self.claim(actor, project_id, claim_id)
        review_id = str(uuid4())
        with self.repo.database.transaction() as connection:
            connection.execute(
                "INSERT INTO reviews VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    review_id,
                    project_id,
                    claim_id,
                    data.get("actor", str(actor)),
                    data["stance"],
                    data["reason"],
                    dumps(data.get("assumptions", [])),
                    data.get("confidence", 0.5),
                    data["independence_group"],
                    now(),
                ),
            )
            self.repo.append_event(
                connection,
                ResearchEvent(
                    project_id=UUID(project_id), actor_id=str(actor), event_type="REVIEW_ATTACHED", payload={"review_id": review_id, "claim_id": claim_id, "stance": data["stance"]}
                ),
            )
        self.recalculate_confidence(project_id, claim_id)
        return self.repo.one("SELECT * FROM reviews WHERE id=?", (review_id,))

    def recalculate_confidence(self, project_id: str, claim_id: str) -> dict:
        signals = []
        for evidence in self.repo.all("SELECT * FROM evidence WHERE claim_id=?", (claim_id,)):
            weight = min(0.25, 0.2 * float(evidence["reliability"]))
            if evidence["evidence_type"] == "formal_verification":
                weight = 0.5
            if evidence["evidence_type"] == "counterexample":
                weight = 0.9
            signals.append(Signal(evidence["evidence_type"], weight, evidence["stance"] == "supports", evidence["source"], evidence["title"]))
        for review in self.repo.all("SELECT * FROM reviews WHERE claim_id=?", (claim_id,)):
            signals.append(Signal("independent_review", 0.08 * float(review["confidence"]), review["stance"] == "agree", review["actor"], review["reason"]))
        result = calculate_with_explanation(signals)
        self.repo.execute("UPDATE claims SET confidence=?,updated_at=? WHERE id=?", (result["score"], now(), claim_id))
        return result

    def invalidate_descendants(self, actor: UUID, project_id: str, node_id: str) -> list[str]:
        graph = self.graph(actor, project_id)
        outgoing: dict[str, set[str]] = {}
        for edge in graph["edges"]:
            if edge["edge_type"] == "depends_on":
                outgoing.setdefault(edge["target_id"], set()).add(edge["source_id"])
        queue, affected = list(outgoing.get(node_id, set())), []
        while queue:
            current = queue.pop(0)
            if current in affected:
                continue
            affected.append(current)
            queue.extend(outgoing.get(current, set()))
        with self.repo.database.transaction() as connection:
            for descendant in affected:
                row = connection.execute("SELECT status FROM nodes WHERE id=?", (descendant,)).fetchone()
                if not row:
                    continue
                connection.execute("UPDATE nodes SET status='invalidated',updated_at=? WHERE id=?", (now(), descendant))
                connection.execute("UPDATE claims SET status='invalidated',updated_at=? WHERE node_id=?", (now(), descendant))
            if affected:
                self.repo.append_event(
                    connection,
                    ResearchEvent(
                        project_id=UUID(project_id),
                        actor_id=str(actor),
                        event_type="DESCENDANTS_INVALIDATED",
                        payload={
                            "source_node_id": node_id,
                            "affected_node_ids": affected,
                            "suggested_reruns": sorted(
                                {x["run_id"] for x in self.repo.all("SELECT id,run_id FROM nodes WHERE project_id=?", (project_id,)) if x["id"] in affected and x["run_id"]}
                            ),
                        },
                    ),
                )
        return affected

    def explanation(self, actor: UUID, project_id: str, claim_id: str) -> dict:
        claim = self.claim(actor, project_id, claim_id)
        evidence = self.repo.all("SELECT * FROM evidence WHERE claim_id=? ORDER BY created_at", (claim_id,))
        reviews = self.repo.all("SELECT * FROM reviews WHERE claim_id=? ORDER BY created_at", (claim_id,))
        for item in evidence:
            for key in ("content", "reproducibility", "assumptions"):
                item[key] = loads(item[key], {} if key != "assumptions" else [])
        confidence = self.recalculate_confidence(project_id, claim_id)
        graph = self.graph(actor, project_id)
        related = [e for e in graph["edges"] if e["source_id"] == claim["node_id"] or e["target_id"] == claim["node_id"]]
        downstream = [e["source_id"] for e in related if e["edge_type"] == "depends_on" and e["target_id"] == claim["node_id"]]
        return {
            "claim": claim,
            "supporting_evidence": [x for x in evidence if x["stance"] == "supports"],
            "contradicting_evidence": [x for x in evidence if x["stance"] == "contradicts"],
            "independent_reviews": reviews,
            "symbolic_checks": [x for x in evidence if x["evidence_type"] == "symbolic_verification"],
            "numerical_checks": [x for x in evidence if x["evidence_type"] == "numerical_test"],
            "formal_verification": [x for x in evidence if x["evidence_type"] == "formal_verification"],
            "failed_proof_attempts": self.repo.all("SELECT * FROM dead_ends WHERE target_id=?", (claim_id,)),
            "unresolved_warnings": [x["title"] for x in evidence if x["stance"] == "contradicts"],
            "downstream_node_ids": downstream,
            "confidence": confidence,
            "causal_paths": related,
        }

    def record_dead_end(self, actor: UUID, project_id: str, data: dict) -> dict:
        self._project(actor, project_id, True)
        dead_id, node_id, timestamp = str(uuid4()), str(uuid4()), now()
        normalized = normalize(data["approach"])
        fp = fingerprint(data["approach"], data.get("assumptions", []), data.get("method", ""))
        search = " ".join([data["approach"], data.get("method", ""), data["failure"], *data.get("assumptions", [])])
        branch = data.get("branch_id") or self.repo.one("SELECT id FROM branches WHERE project_id=? AND name='main'", (project_id,))["id"]
        with self.repo.database.transaction() as connection:
            connection.execute(
                "INSERT INTO nodes VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    node_id,
                    project_id,
                    branch,
                    data.get("run_id"),
                    "dead_end",
                    data["approach"],
                    dumps(data),
                    "failed",
                    dumps({"x": 0, "y": 0}),
                    dumps({"actor": str(actor), "fingerprint": fp}),
                    1,
                    timestamp,
                    timestamp,
                ),
            )
            connection.execute(
                "INSERT INTO dead_ends VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    dead_id,
                    project_id,
                    branch,
                    data.get("run_id"),
                    node_id,
                    data.get("target_id"),
                    data["approach"],
                    normalized,
                    dumps(data.get("assumptions", [])),
                    data.get("method", ""),
                    data["failure"],
                    data["lesson"],
                    data.get("applies_where", ""),
                    data.get("may_not_apply_where", ""),
                    data.get("discovered_by", str(actor)),
                    fp,
                    search,
                    timestamp,
                ),
            )
            self.repo.append_event(
                connection,
                ResearchEvent(
                    project_id=UUID(project_id),
                    branch_id=UUID(branch),
                    actor_id=str(actor),
                    event_type="DEAD_END_RECORDED",
                    payload={"dead_end_id": dead_id, "node_id": node_id, "fingerprint": fp},
                ),
            )
        return self.repo.one("SELECT * FROM dead_ends WHERE id=?", (dead_id,))

    def search_dead_ends(self, actor: UUID, query: str, project_id: str | None = None, threshold: float = 0.18) -> list[dict]:
        if project_id:
            self._project(actor, project_id)
        rows = self.repo.all(
            """SELECT d.* FROM dead_ends d JOIN projects p ON p.id=d.project_id LEFT JOIN project_members pm ON pm.project_id=p.id AND pm.user_id=? WHERE (p.owner_id=? OR pm.user_id=? OR p.visibility='public')""",
            (str(actor), str(actor), str(actor)),
        )
        matches = []
        for row in rows:
            if project_id and row["project_id"] != project_id:
                continue
            score = self.similarity.score(query, row["search_text"])
            if score >= threshold or normalize(query) in normalize(row["search_text"]):
                row["similarity"] = round(max(score, 0.5 if normalize(query) in normalize(row["search_text"]) else score), 4)
                matches.append(row)
        return sorted(matches, key=lambda x: -x["similarity"])

    def save_pipeline(self, actor: UUID, project_id: str, data: dict, pipeline_id: str | None = None) -> dict:
        self._project(actor, project_id, True)
        validation = self.validate_pipeline(data, actor)
        if not validation["valid"]:
            raise ValidationError("; ".join(validation["errors"]))
        timestamp = now()
        pipeline_id = pipeline_id or str(uuid4())
        existing = self.repo.one("SELECT * FROM pipelines WHERE id=?", (pipeline_id,))
        with self.repo.database.transaction() as connection:
            if existing:
                connection.execute("UPDATE pipelines SET name=?,version=version+1,definition=?,updated_at=? WHERE id=?", (data["name"], dumps(data), timestamp, pipeline_id))
            else:
                connection.execute("INSERT INTO pipelines VALUES(?,?,?,?,?,?,?,?)", (pipeline_id, project_id, data["name"], 1, dumps(data), str(actor), timestamp, timestamp))
            self.repo.append_event(
                connection,
                ResearchEvent(
                    project_id=UUID(project_id),
                    actor_id=str(actor),
                    event_type="PIPELINE_UPDATED" if existing else "PIPELINE_CREATED",
                    payload={"pipeline_id": pipeline_id, "name": data["name"]},
                ),
            )
        return self.get_pipeline(actor, pipeline_id)

    def validate_pipeline(self, data: dict, actor: UUID | None = None) -> dict:
        errors, warnings = [], []
        nodes = {n["id"]: n for n in data.get("nodes", [])}
        if len(nodes) != len(data.get("nodes", [])):
            errors.append("Pipeline node IDs must be unique")
        adjacency = {k: [] for k in nodes}
        incoming = {k: 0 for k in nodes}
        edge_keys = set()
        for edge in data.get("edges", []):
            if edge.get("source") not in nodes or edge.get("target") not in nodes:
                errors.append("Edge references a missing node")
                continue
            edge_key = (edge["source"], edge["target"])
            if edge_key in edge_keys:
                errors.append("Pipeline contains a duplicate edge")
            edge_keys.add(edge_key)
            if edge["source"] == edge["target"]:
                errors.append("Pipeline nodes cannot connect to themselves")
            adjacency[edge["source"]].append(edge["target"])
            incoming[edge["target"]] += 1
        for node in nodes.values():
            config = node.get("config", {})
            plugin_id = config.get("plugin")
            provider = config.get("provider")
            if plugin_id and self.plugin_registry:
                try:
                    manifest = self.plugin_registry.get(plugin_id).manifest
                    if manifest.permissions or manifest.network_domains or manifest.filesystem_access not in {"none", "temporary"}:
                        warnings.append(f"Plugin {plugin_id} requests elevated sandbox permissions")
                except KeyError:
                    errors.append(f"Plugin {plugin_id} is missing or disabled")
            if provider:
                if provider not in self.provider_metadata:
                    errors.append(f"Provider {provider} is unsupported")
                elif actor:
                    _, credential = self.resolve_secret(actor, provider, self.platform_keys)
                    if credential["source"] == "unavailable":
                        warnings.append(f"Provider {provider} has no configured credential")
                if provider == "generic" and not config.get("endpoint_id"):
                    errors.append("Generic provider nodes require an allowlisted endpoint_id")
            retry = config.get("retry_policy", {})
            if retry and (not isinstance(retry.get("max_attempts", 1), int) or not 1 <= retry.get("max_attempts", 1) <= 10):
                errors.append(f"Node {node['id']} has an invalid retry policy")
            if incoming.get(node["id"], 0) > 1 and config.get("branch_behavior") not in {"merge", "all", "any"}:
                warnings.append(f"Join node {node['id']} should declare branch_behavior")
        state = {k: 0 for k in nodes}

        def visit(key):
            state[key] = 1
            for child in adjacency[key]:
                if state[child] == 1:
                    return True
                if state[child] == 0 and visit(child):
                    return True
            state[key] = 2
            return False

        if any(state[k] == 0 and visit(k) for k in nodes):
            errors.append("Pipeline contains a cycle")
        if nodes:
            roots = [k for k, count in incoming.items() if count == 0]
            seen, queue = set(), roots[:]
            while queue:
                key = queue.pop()
                seen.add(key)
                queue.extend(x for x in adjacency[key] if x not in seen)
            if len(seen) != len(nodes):
                errors.append("Pipeline contains unreachable nodes")
        if not nodes:
            warnings.append("Blank pipeline has no executable nodes")
        return {
            "valid": not errors,
            "errors": errors,
            "warnings": warnings,
            "estimated_max_cost_micros": sum(int(n.get("config", {}).get("cost_cap_micros", 0)) for n in nodes.values()),
        }

    def get_pipeline(self, actor: UUID, pipeline_id: str) -> dict:
        row = self.repo.one("SELECT * FROM pipelines WHERE id=?", (pipeline_id,))
        if not row:
            raise NotFoundError("Pipeline not found")
        self._project(actor, row["project_id"])
        row["definition"] = loads(row["definition"], {})
        return row

    def pipelines(self, actor: UUID, project_id: str) -> list[dict]:
        self._project(actor, project_id)
        rows = self.repo.all("SELECT * FROM pipelines WHERE project_id=? ORDER BY updated_at DESC", (project_id,))
        for row in rows:
            row["definition"] = loads(row["definition"], {})
        return rows

    def duplicate_pipeline(self, actor: UUID, pipeline_id: str) -> dict:
        original = self.get_pipeline(actor, pipeline_id)
        definition = original["definition"]
        definition["name"] = definition["name"] + " (copy)"
        return self.save_pipeline(actor, original["project_id"], definition)

    def delete_pipeline(self, actor: UUID, pipeline_id: str) -> None:
        pipeline = self.get_pipeline(actor, pipeline_id)
        self._project(actor, pipeline["project_id"], True)
        self.repo.execute("DELETE FROM pipelines WHERE id=?", (pipeline_id,))

    def create_run(self, actor: UUID, project_id: str, data: dict) -> dict:
        self._project(actor, project_id, True)
        run_id, timestamp = str(uuid4()), now()
        mode = data.get("execution_mode", "mock")
        if mode == "live" and not data.get("pipeline_id"):
            raise ValidationError("Live runs require a persisted pipeline")
        with self.repo.database.transaction() as connection:
            connection.execute(
                "INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    run_id,
                    project_id,
                    data.get("pipeline_id"),
                    data.get("branch_id"),
                    "draft",
                    data["goal"],
                    mode,
                    dumps({"stage": "QUESTION", "completed_nodes": [], "use_default_contract": bool(data.get("use_default_contract", False))}),
                    str(actor),
                    timestamp,
                    timestamp,
                ),
            )
            self.repo.append_event(
                connection,
                ResearchEvent(
                    project_id=UUID(project_id),
                    run_id=UUID(run_id),
                    actor_id=str(actor),
                    event_type="RUN_CREATED",
                    payload={"run_id": run_id, "goal": data["goal"], "execution_mode": mode},
                ),
            )
        return self.run(actor, run_id)

    def run(self, actor: UUID, run_id: str) -> dict:
        row = self.repo.one("SELECT * FROM runs WHERE id=?", (run_id,))
        if not row:
            raise NotFoundError("Run not found")
        self._project(actor, row["project_id"])
        row["checkpoint"] = loads(row["checkpoint"], {})
        return row

    def run_steps(self, actor: UUID, run_id: str) -> list[dict]:
        self.run(actor, run_id)
        rows = self.repo.all("SELECT * FROM run_steps WHERE run_id=? ORDER BY started_at, pipeline_node_id", (run_id,))
        for row in rows:
            row["input"] = loads(row["input"], {})
            row["output"] = loads(row["output"], {}) if row.get("output") else None
        return rows

    def set_run_status(self, actor: UUID, run_id: str, action: str) -> dict:
        run = self.run(actor, run_id)
        transitions = {
            "start": ({"draft", "queued"}, "running", "RUN_STARTED"),
            "pause": ({"running"}, "paused", "RUN_PAUSED"),
            "resume": ({"paused", "waiting_for_user"}, "running", "RUN_RESUMED"),
            "cancel": ({"draft", "queued", "running", "paused", "waiting_for_user"}, "cancelled", "RUN_CANCELLED"),
        }
        allowed, status, event = transitions[action]
        if run["status"] not in allowed:
            raise ConflictError(f"Cannot {action} a {run['status']} run")
        with self.repo.database.transaction() as connection:
            connection.execute("UPDATE runs SET status=?,updated_at=? WHERE id=?", (status, now(), run_id))
            self.repo.append_event(
                connection,
                ResearchEvent(
                    project_id=UUID(run["project_id"]), run_id=UUID(run_id), actor_id=str(actor), event_type=event, payload={"previous": run["status"], "status": status}
                ),
            )
        return self.run(actor, run_id)

    def save_credential(self, actor: UUID, provider: str, plaintext: str, rotate: bool = False) -> dict:
        allowed = {"openai", "anthropic", "google", "deepseek", "xai", "ollama", "generic", "mock"}
        if provider not in allowed:
            raise ValidationError("Unsupported provider")
        if provider in {"ollama", "mock"}:
            raise ValidationError("Local/mock providers do not accept API credentials")
        encrypted = self.vault.encrypt(plaintext)
        fp = hashlib.sha256(plaintext.encode()).hexdigest()[:12]
        timestamp = now()
        existing = self.repo.one("SELECT id FROM provider_credentials WHERE user_id=? AND provider=?", (str(actor), provider))
        cred_id = existing["id"] if existing else str(uuid4())
        with self.repo.database.transaction() as connection:
            connection.execute(
                "INSERT INTO provider_credentials VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(user_id,provider) DO UPDATE SET encrypted_key=excluded.encrypted_key,key_fingerprint=excluded.key_fingerprint,status='active',updated_at=excluded.updated_at",
                (cred_id, str(actor), provider, encrypted, fp, "active", None, timestamp, timestamp),
            )
        self._security_audit(str(actor), "credential_rotated" if rotate or existing else "credential_stored", None, {"provider": provider, "fingerprint": fp})
        return {"provider": provider, "status": "active", "key_hint": "••••" + plaintext[-4:], "fingerprint": fp}

    def list_credentials(self, actor: UUID) -> list[dict]:
        return self.repo.all("SELECT provider,status,key_fingerprint,last_used_at,created_at,updated_at FROM provider_credentials WHERE user_id=? ORDER BY provider", (str(actor),))

    def delete_credential(self, actor: UUID, provider: str) -> None:
        row = self.repo.one("SELECT encrypted_key FROM provider_credentials WHERE user_id=? AND provider=?", (str(actor), provider))
        if row:
            self.vault.delete(row["encrypted_key"])
        with self.repo.database.transaction() as connection:
            connection.execute("DELETE FROM provider_credentials WHERE user_id=? AND provider=?", (str(actor), provider))
        self._security_audit(str(actor), "credential_deleted", None, {"provider": provider})

    def _security_audit(self, user_id: str | None, event_type: str, remote: str | None, detail: dict) -> None:
        remote_hash = hashlib.sha256(remote.encode()).hexdigest() if remote else None
        self.repo.execute("INSERT INTO security_audit VALUES(?,?,?,?,?,?)", (str(uuid4()), user_id, event_type, remote_hash, dumps(detail), now()))

    def resolve_secret(self, actor: UUID, provider: str, platform_keys: dict[str, str]) -> tuple[str | None, dict]:
        row = self.repo.one("SELECT encrypted_key FROM provider_credentials WHERE user_id=? AND provider=? AND status='active'", (str(actor), provider))
        if row:
            return self.vault.decrypt(row["encrypted_key"]), {"source": "byok", "billable_by_orchestra": False}
        if platform_keys.get(provider):
            return platform_keys[provider], {"source": "platform", "billable_by_orchestra": True}
        if provider in {"ollama", "mock"}:
            return None, {"source": "local", "billable_by_orchestra": False}
        return None, {"source": "unavailable", "billable_by_orchestra": False}

    def balance(self, actor: UUID) -> dict:
        row = self.repo.one("SELECT COALESCE(SUM(amount_micros),0) amount FROM ledger_entries WHERE user_id=?", (str(actor),))
        reserved = self.repo.one("SELECT COALESCE(SUM(reserved_micros-settled_micros),0) amount FROM credit_reservations WHERE user_id=? AND status IN ('reserved','reconciliation_required')", (str(actor),))
        return {"currency": "USD", "balance_micros": row["amount"], "available_micros": row["amount"] - reserved["amount"], "reserved_micros": reserved["amount"]}

    def add_credits(self, actor: UUID, amount_micros: int, reason: str = "admin_test_credit") -> dict:
        entry = str(uuid4())
        self.repo.execute("INSERT INTO ledger_entries VALUES(?,?,?,?,?,?,?,?)", (entry, str(actor), None, "credit", amount_micros, "USD", dumps({"reason": reason}), now()))
        return self.balance(actor)

    def reserve_credits(self, actor: UUID, run_id: str, maximum_micros: int) -> dict:
        if maximum_micros <= 0:
            raise ValidationError("Reservation must be positive")
        reservation_id, timestamp = str(uuid4()), now()
        run = self.run(actor, run_id)
        with self.repo.database.transaction() as connection:
            if self.repo.database.is_postgres:
                connection.execute("SELECT id FROM users WHERE id=? FOR UPDATE", (str(actor),)).fetchone()
            credited = connection.execute("SELECT COALESCE(SUM(amount_micros),0) amount FROM ledger_entries WHERE user_id=?", (str(actor),)).fetchone()["amount"]
            reserved = connection.execute(
                "SELECT COALESCE(SUM(reserved_micros-settled_micros),0) amount FROM credit_reservations WHERE user_id=? AND status IN ('reserved','reconciliation_required')",
                (str(actor),),
            ).fetchone()["amount"]
            if credited - reserved < maximum_micros:
                raise InsufficientCreditsError("Insufficient Orchestra Credits")
            connection.execute("INSERT INTO credit_reservations VALUES(?,?,?,?,?,?,?,?)", (reservation_id, str(actor), run_id, maximum_micros, 0, "reserved", timestamp, timestamp))
            self.repo.append_event(
                connection,
                ResearchEvent(
                    project_id=UUID(run["project_id"]),
                    run_id=UUID(run_id),
                    actor_id=str(actor),
                    event_type="CREDITS_RESERVED",
                    payload={"reservation_id": reservation_id, "maximum_micros": maximum_micros},
                ),
            )
        return {"id": reservation_id, "reserved_micros": maximum_micros, "status": "reserved"}

    def settle_credits(self, actor: UUID, reservation_id: str, actual_micros: int) -> dict:
        reservation = self.repo.one("SELECT * FROM credit_reservations WHERE id=? AND user_id=?", (reservation_id, str(actor)))
        if not reservation:
            raise NotFoundError("Active reservation not found")
        run = self.run(actor, reservation["run_id"])
        with self.repo.database.transaction() as connection:
            suffix = " FOR UPDATE" if self.repo.database.is_postgres else ""
            reservation = connection.execute(
                "SELECT * FROM credit_reservations WHERE id=? AND user_id=?" + suffix,
                (reservation_id, str(actor)),
            ).fetchone()
            if not reservation or reservation["status"] not in {"reserved", "reconciliation_required"}:
                raise NotFoundError("Active reservation not found")
            if actual_micros < 0 or actual_micros > reservation["reserved_micros"]:
                raise ValidationError("Settlement exceeds reservation")
            if actual_micros:
                connection.execute(
                    "INSERT INTO ledger_entries VALUES(?,?,?,?,?,?,?,?)",
                    (str(uuid4()), str(actor), reservation["run_id"], "usage", -actual_micros, "USD", dumps({"reservation_id": reservation_id}), now()),
                )
            connection.execute("UPDATE credit_reservations SET settled_micros=?,status='settled',updated_at=? WHERE id=?", (actual_micros, now(), reservation_id))
            self.repo.append_event(
                connection,
                ResearchEvent(
                    project_id=UUID(run["project_id"]),
                    run_id=UUID(run["id"]),
                    actor_id=str(actor),
                    event_type="CREDITS_SETTLED",
                    payload={"reservation_id": reservation_id, "actual_micros": actual_micros},
                ),
            )
            self.repo.append_event(
                connection,
                ResearchEvent(
                    project_id=UUID(run["project_id"]),
                    run_id=UUID(run["id"]),
                    actor_id=str(actor),
                    event_type="CREDITS_RELEASED",
                    payload={"reservation_id": reservation_id, "released_micros": reservation["reserved_micros"] - actual_micros},
                ),
            )
        return self.balance(actor)

    def publish(self, actor: UUID, project_id: str) -> dict:
        project = self._project(actor, project_id, True)
        graph = self.graph(actor, project_id)
        events = self.repo.events(project_id=project_id)
        version_row = self.repo.one("SELECT COALESCE(MAX(version),0)+1 version FROM public_snapshots WHERE project_id=?", (project_id,))
        snapshot_id = "snap_" + uuid4().hex
        safe_project = {k: project[k] for k in ("id", "title", "question", "abstract", "status", "tags", "created_at", "updated_at")}
        payload = {
            "schema_version": "1.0",
            "snapshot_id": snapshot_id,
            "version": version_row["version"],
            "project": safe_project,
            "graph": graph,
            "epistemic_contract": next(
                (node["content"] for node in graph["nodes"] if node["kind"] == "human_review" and node["title"] == "Epistemic Contract"),
                None,
            ),
            "pipelines": self.pipelines(actor, project_id),
            "claims": self.repo.all("SELECT id,node_id,statement,latex,assumptions,status,confidence,proposed_by FROM claims WHERE project_id=?", (project_id,)),
            "evidence": self.repo.all(
                "SELECT id,node_id,claim_id,evidence_type,stance,title,content,source,reliability,reproducibility,immutable_hash,created_at FROM evidence WHERE project_id=?",
                (project_id,),
            ),
            "dead_ends": self.repo.all("SELECT id,node_id,target_id,approach,assumptions,method,failure,lesson,created_at FROM dead_ends WHERE project_id=?", (project_id,)),
            "literature": self.repo.all("SELECT * FROM literature_sources WHERE project_id=?", (project_id,)),
            "replay": events,
        }
        encoded = dumps(payload)
        integrity = hashlib.sha256(encoded.encode()).hexdigest()
        with self.repo.database.transaction() as connection:
            connection.execute("INSERT INTO public_snapshots VALUES(?,?,?,?,?,?,?)", (snapshot_id, project_id, version_row["version"], encoded, integrity, 1, now()))
            connection.execute("UPDATE projects SET visibility='public',updated_at=? WHERE id=?", (now(), project_id))
            self.repo.append_event(
                connection,
                ResearchEvent(
                    project_id=UUID(project_id),
                    actor_id=str(actor),
                    event_type="PUBLIC_SNAPSHOT_CREATED",
                    payload={"snapshot_id": snapshot_id, "version": version_row["version"], "integrity_hash": integrity},
                ),
            )
        return {"snapshot_id": snapshot_id, "version": version_row["version"], "integrity_hash": integrity}

    def public_snapshot(self, snapshot_id: str) -> dict:
        bundled = bundled_public_snapshot(snapshot_id)
        if bundled:
            return bundled
        row = self.repo.one("SELECT * FROM public_snapshots WHERE id=? AND visible=1", (snapshot_id,))
        if not row:
            raise NotFoundError("Public snapshot not found")
        return {"id": row["id"], "version": row["version"], "integrity_hash": row["integrity_hash"], "created_at": row["created_at"], "payload": loads(row["payload"], {})}

    def unpublish(self, actor: UUID, project_id: str) -> dict:
        self._project(actor, project_id, True)
        with self.repo.database.transaction() as connection:
            connection.execute("UPDATE public_snapshots SET visible=0 WHERE project_id=?", (project_id,))
            connection.execute("UPDATE projects SET visibility='private',updated_at=? WHERE id=?", (now(), project_id))
        return {"status": "unpublished"}

    def public_projects(self) -> list[dict]:
        rows = self.repo.all(
            """SELECT p.id,p.title,p.question,p.abstract,p.tags,p.created_at,p.updated_at,
            (SELECT s.id FROM public_snapshots s WHERE s.project_id=p.id AND s.visible=1 ORDER BY s.version DESC LIMIT 1) snapshot_id
            FROM projects p WHERE p.visibility='public' ORDER BY p.updated_at DESC"""
        )
        for row in rows:
            row["tags"] = loads(row["tags"], [])
        bundled = bundled_public_projects()
        bundled_ids = {row["id"] for row in bundled}
        return bundled + [row for row in rows if row["id"] not in bundled_ids]

    def add_literature(self, actor: UUID, project_id: str, data: dict) -> dict:
        self._project(actor, project_id, True)
        source_id = str(uuid4())
        with self.repo.database.transaction() as connection:
            connection.execute(
                "INSERT INTO literature_sources VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    source_id,
                    project_id,
                    data["source_type"],
                    data["title"],
                    dumps(data.get("authors", [])),
                    data.get("doi"),
                    data.get("arxiv_id"),
                    data.get("url"),
                    dumps(data.get("metadata", {})),
                    data.get("reliability", 0.5),
                    now(),
                ),
            )
            self.repo.append_event(
                connection, ResearchEvent(project_id=UUID(project_id), actor_id=str(actor), event_type="LITERATURE_ADDED", payload={"source_id": source_id, "title": data["title"]})
            )
        return self.repo.one("SELECT * FROM literature_sources WHERE id=?", (source_id,))

    def controversial_claims(self, actor: UUID, project_id: str) -> list[dict]:
        self._project(actor, project_id)
        return self.repo.all(
            """SELECT c.id,c.statement,c.status,c.confidence,
            SUM(CASE WHEN r.stance='agree' THEN 1 ELSE 0 END) agrees,
            SUM(CASE WHEN r.stance='disagree' THEN 1 ELSE 0 END) disagrees
            FROM claims c JOIN reviews r ON r.claim_id=c.id WHERE c.project_id=? GROUP BY c.id
            HAVING agrees>0 AND disagrees>0 ORDER BY (agrees+disagrees) DESC""",
            (project_id,),
        )

    def record_benchmark(self, actor: UUID, task_id: str, mode: str, metrics: dict) -> dict:
        allowed = {
            "correct_counterexamples",
            "algebra_verified",
            "formal_proof_success",
            "repeated_dead_ends",
            "reproducibility",
            "evidence_coverage",
            "provenance_completeness",
            "cost_micros",
            "latency_ms",
            "revisions",
            "human_interventions",
        }
        if not set(metrics).issubset(allowed):
            raise ValidationError("Unknown benchmark metric")
        benchmark_id = str(uuid4())
        self.repo.execute("INSERT INTO benchmark_runs VALUES(?,?,?,?,?,?)", (benchmark_id, str(actor), task_id, mode, dumps(metrics), now()))
        return {"id": benchmark_id, "task_id": task_id, "mode": mode, "metrics": metrics}

    def replay(self, actor: UUID, project_id: str | None = None, run_id: str | None = None) -> dict:
        if run_id:
            run = self.run(actor, run_id)
            project_id = run["project_id"]
        self._project(actor, project_id)
        events = self.repo.events(project_id=project_id, run_id=run_id)
        valid = all(hashlib.sha256(dumps({k: v for k, v in event.items() if k != "integrity_hash"}).encode()).hexdigest() for event in events)
        return {"project_id": project_id, "run_id": run_id, "events": events, "event_count": len(events), "chronological": True, "integrity_present": valid}
