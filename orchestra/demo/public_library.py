"""Immutable, account-free public-library showcase for a clean judge install."""

from __future__ import annotations

import copy
import hashlib
import json
from functools import lru_cache
from typing import Any

PROJECT_ID = "demo-signed-monomials"
SNAPSHOT_ID = "snap_demo_signed_monomials_v1"
CREATED_AT = "2026-07-20T18:46:20+00:00"


def _node(node_id: str, kind: str, title: str, status: str, content: dict[str, Any], provenance: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": node_id,
        "project_id": PROJECT_ID,
        "branch_id": None,
        "run_id": None,
        "kind": kind,
        "title": title,
        "content": content,
        "status": status,
        "position": {"x": 0.0, "y": 0.0},
        "provenance": provenance,
        "version": 1,
        "created_at": CREATED_AT,
        "updated_at": CREATED_AT,
    }


def _edge(edge_id: str, source_id: str, target_id: str, edge_type: str) -> dict[str, Any]:
    return {
        "id": edge_id,
        "project_id": PROJECT_ID,
        "branch_id": None,
        "source_id": source_id,
        "target_id": target_id,
        "edge_type": edge_type,
        "metadata": {},
        "created_at": CREATED_AT,
    }


def _event(event_type: str, payload: dict[str, Any], sequence: int, actor_type: str = "user") -> dict[str, Any]:
    return {
        "id": f"demo-event-{sequence:02d}",
        "project_id": PROJECT_ID,
        "run_id": None,
        "branch_id": "demo-main",
        "actor_id": "demo-researcher",
        "actor_type": actor_type,
        "event_type": event_type,
        "payload": payload,
        "parent_event_id": None,
        "correlation_id": "demo-signed-monomials",
        "idempotency_key": None,
        "schema_version": "1.0",
        "integrity_hash": None,
        "timestamp": f"2026-07-20T18:46:{20 + sequence:02d}+00:00",
    }


@lru_cache(maxsize=1)
def _snapshot() -> dict[str, Any]:
    contract = {
        "evidence_standard": "At least one directly relevant source or reproducible result must support each material claim.",
        "falsification_criteria": "Actively search for counterexamples, contradictory findings, and assumptions that would make the claim fail.",
        "source_requirements": "Prefer primary sources. Preserve stable identifiers and distinguish source statements from model interpretation.",
        "verification_requirements": "Use Lean for formal statements and SymPy or reproducible computation for algebraic or numerical claims where applicable.",
        "human_checkpoints": "The researcher approves the contract, resolves material conflicts, and signs off before a conclusion is treated as accepted.",
    }
    question_id = "demo-question"
    route_a_id = "demo-route-sign-profile"
    route_b_id = "demo-route-walsh"
    route_c_id = "demo-route-direct-expansion"
    claim_id = "demo-claim-parity-state"
    objection_id = "demo-objection-non-affine"
    evidence_id = "demo-evidence-character-orthogonality"
    sympy_id = "demo-check-sympy"
    lean_id = "demo-check-lean"
    conclusion_id = "demo-conclusion-affine-count"
    report_id = "demo-report"
    contract_id = "demo-epistemic-contract"

    nodes = [
        _node(
            question_id,
            "question",
            "Count surviving monomials without brute-force expansion",
            "open",
            {
                "statement": "Characterize and enumerate monomials with nonzero total coefficient in Σₜ(sₜ·x)ᵈ.",
                "unknowns": [
                    "Which sign structures factor?",
                    "What parity constraints govern survival?",
                    "How are admissible exponent allocations counted?",
                ],
            },
            {"actor": "researcher", "execution_mode": "guided-rehearsal"},
        ),
        _node(
            contract_id,
            "human_review",
            "Epistemic Contract",
            "accepted",
            contract,
            {"actor": "demo-researcher", "authority": "researcher", "immutable_intent": True},
        ),
        _node(
            route_a_id,
            "hypothesis",
            "Route A · sign-profile partition",
            "proposed",
            {"proposal": "Group variables by their complete sign histories, then count exponent totals per group."},
            {"provider": "openai", "model": "gpt-5.6", "execution_mode": "guided-rehearsal"},
        ),
        _node(
            route_b_id,
            "hypothesis",
            "Route B · Walsh character sum",
            "proposed",
            {"proposal": "Encode signs over F₂ and interpret cancellation through character orthogonality."},
            {"provider": "anthropic", "model": "claude-sonnet-4-5", "execution_mode": "guided-rehearsal"},
        ),
        _node(
            route_c_id,
            "unexplored_branch",
            "Route C · direct symbolic expansion",
            "unexplored",
            {
                "proposal": "Expand every signed multinomial and compare coefficients.",
                "reason_preserved": "Useful as a finite check but not an optimal general proof strategy.",
            },
            {"provider": "google", "model": "gemini-2.5-pro", "execution_mode": "guided-rehearsal"},
        ),
        _node(
            claim_id,
            "claim",
            "Coefficient survival reduces to a parity-state function",
            "under_test",
            {
                "statement": "For group exponent vector e, a monomial survives iff C(e)=Σₜ∏g σₜg^e_g ≠ 0.",
                "assumptions": ["Identical sign profiles are grouped", "All multinomial weights are +1"],
            },
            {"role": "route-comparator", "execution_mode": "guided-rehearsal"},
        ),
        _node(
            objection_id,
            "contradiction",
            "Non-affine sign rows need not factor",
            "unresolved",
            {
                "objection": "C(e) remains a character sum, but arbitrary row sets do not necessarily yield independent linear parity constraints.",
                "example": "{000,100,010,111}",
            },
            {"provider": "anthropic", "role": "independent-skeptic", "execution_mode": "guided-rehearsal"},
        ),
        _node(
            evidence_id,
            "evidence",
            "Affine-subspace character orthogonality",
            "supported",
            {
                "result": "For H=v₀+U, the character sum vanishes off U⊥ and equals ±|U| on U⊥.",
                "method": "finite-group character calculation",
            },
            {"provider": "openai", "execution_mode": "guided-rehearsal"},
        ),
        _node(
            sympy_id,
            "computation",
            "SymPy checks r=2, r=4, and r=8 examples",
            "independently_confirmed",
            {
                "checks": [
                    "Two expansions: one even-parity constraint",
                    "Four expansions: e₂,e₃,e₄ share parity",
                    "Eight-expansion degree-4 cube: 10 surviving monomials",
                ],
                "reproducible": True,
            },
            {"plugin": "core.sympy", "execution_mode": "local"},
        ),
        _node(
            lean_id,
            "formal_verification",
            "Lean-checkable parity factorization lemmas",
            "formally_verified",
            {
                "scope": "Binary parity identities and finite products; semantic match remains researcher-reviewed.",
                "verification_status": "formally_verified",
            },
            {"plugin": "core.lean", "execution_mode": "local"},
        ),
        _node(
            conclusion_id,
            "conclusion",
            "Affine sign structures yield explicit surviving-monomial counts",
            "independently_confirmed",
            {
                "statement": "If the binary sign rows form an affine k-dimensional subspace, survival is exactly a system of k linear parity equations; admissible group exponent vectors are then counted by weighted Stars and Bars.",
                "formula": "N(d)=Σ_{e∈S(d)} ∏ᵢ binom(eᵢ+vᵢ−1,vᵢ−1)",
                "boundary": "A converse classification and general non-affine enumeration remain open.",
            },
            {"synthesis": ["openai", "anthropic", "google", "core.sympy", "core.lean", "researcher"], "execution_mode": "guided-rehearsal"},
        ),
        _node(
            report_id,
            "human_review",
            "Generated research report · signed multinomial parity",
            "accepted",
            {
                "title": "Counting Surviving Monomials in Signed Multinomial Sums via Parity Constraints",
                "abstract": "Variables are partitioned by complete sign profile. Their group exponent sums determine a finite character sum C(e). For affine binary sign rows, character orthogonality turns survival into linear parity constraints; weighted Stars and Bars then counts the surviving monomials.",
                "principal_result": "For an affine k-dimensional sign configuration, C(e) is nonzero exactly on the orthogonal parity subspace.",
                "verification_summary": [
                    "The r=2 formula reduces to one even-parity constraint.",
                    "The r=4 affine square forces e₂,e₃,e₄ to share parity.",
                    "The degree-4 r=8 affine cube has exactly 10 surviving monomials.",
                    "Lean checks scoped parity lemmas; semantic correspondence remains researcher-reviewed.",
                ],
                "open_questions": [
                    "Classify all non-affine sign matrices with factorable coefficient functions.",
                    "Enumerate perturbations of affine configurations.",
                    "Extend the method to weighted signed sums.",
                ],
                "disclaimer": "Guided rehearsal assembled from researcher-supplied mathematics; novelty and literature priority require external scholarly review.",
            },
            {"authority": "researcher", "generated_by": "Pico Probe report assembler"},
        ),
    ]
    edge_specs = [
        ("route-a", question_id, route_a_id, "motivates"),
        ("route-b", question_id, route_b_id, "motivates"),
        ("route-c", question_id, route_c_id, "motivates"),
        ("support-a", route_a_id, claim_id, "supports"),
        ("support-b", route_b_id, claim_id, "supports"),
        ("critique", objection_id, claim_id, "critiques"),
        ("evidence", evidence_id, claim_id, "supports"),
        ("sympy", sympy_id, claim_id, "verifies"),
        ("lean", lean_id, claim_id, "verifies"),
        ("conclusion", claim_id, conclusion_id, "derives_from"),
        ("report", conclusion_id, report_id, "produces"),
    ]
    edges = [_edge(f"demo-edge-{name}", source, target, relation) for name, source, target, relation in edge_specs]

    pipeline_nodes = [
        {"id": "formalize", "type": "formalization", "config": {"human_input": True, "label": "Formalize the research question"}},
        {"id": "openai_plan", "type": "hypothesis_generation", "config": {"provider": "openai", "model": "gpt-5.6", "label": "OpenAI independent plan"}},
        {"id": "anthropic_plan", "type": "hypothesis_generation", "config": {"provider": "anthropic", "model": "claude-sonnet-4-5", "label": "Claude independent plan"}},
        {"id": "gemini_plan", "type": "hypothesis_generation", "config": {"provider": "google", "model": "gemini-2.5-pro", "label": "Gemini independent plan"}},
        {"id": "elect", "type": "synthesis", "config": {"provider": "openai", "model": "gpt-5.6", "label": "Compare and elect route", "preserve_unselected": True}},
        {"id": "sympy", "type": "plugin", "config": {"plugin": "core.sympy", "label": "SymPy verification"}},
        {"id": "lean", "type": "plugin", "config": {"plugin": "core.lean", "label": "Lean verification"}},
        {"id": "human", "type": "human_review", "config": {"human_input": True, "label": "Researcher sign-off"}},
    ]
    pipeline_edges = [
        {"source": "formalize", "target": "openai_plan"},
        {"source": "formalize", "target": "anthropic_plan"},
        {"source": "formalize", "target": "gemini_plan"},
        {"source": "openai_plan", "target": "elect"},
        {"source": "anthropic_plan", "target": "elect"},
        {"source": "gemini_plan", "target": "elect"},
        {"source": "elect", "target": "sympy"},
        {"source": "elect", "target": "lean"},
        {"source": "sympy", "target": "human"},
        {"source": "lean", "target": "human"},
    ]
    project = {
        "id": PROJECT_ID,
        "title": "Which monomials survive signed multinomial cancellation?",
        "question": "Given P(x)=Σₜ(sₜ·x)ᵈ with sign vectors sₜ∈{±1}ᵐ, can the surviving monomials be characterized and counted without expanding every multinomial?",
        "abstract": "A guided investigation into sign profiles, finite binary geometry, parity constraints, and enumeration. Competing routes are preserved before the qualified affine conclusion is checked.",
        "status": "completed_showcase",
        "tags": ["build-week-showcase", "combinatorics", "signed-multinomials", "parity"],
        "created_at": CREATED_AT,
        "updated_at": "2026-07-20T18:46:53+00:00",
    }
    event_specs = [
        ("PROJECT_CREATED", {"title": project["title"], "question": project["question"]}),
        ("ASSURANCE_CONTRACT_ACCEPTED", {"contract_id": contract_id}),
        ("PIPELINE_CREATED", {"pipeline_id": "demo-independent-route-election", "name": "Independent Route Election + Verification"}),
        ("ROUTES_GENERATED", {"node_ids": [route_a_id, route_b_id, route_c_id], "independent": True}),
        ("ROUTE_ELECTED", {"elected_node_id": route_a_id, "preserved_unexplored_node_ids": [route_b_id, route_c_id]}),
        ("COUNTEREXAMPLE_BOUNDARY_RECORDED", {"node_id": objection_id}),
        ("SYMPY_CHECK_COMPLETED", {"node_id": sympy_id, "status": "independently_confirmed"}),
        ("LEAN_CHECK_COMPLETED", {"node_id": lean_id, "status": "formally_verified"}),
        ("QUALIFIED_CONCLUSION_CREATED", {"node_id": conclusion_id, "boundary_preserved": True}),
        ("HUMAN_REVIEW_ACCEPTED", {"node_id": report_id}),
    ]
    replay = [_event(event_type, event_payload, index + 1) for index, (event_type, event_payload) in enumerate(event_specs)]
    payload = {
        "schema_version": "1.0",
        "snapshot_id": SNAPSHOT_ID,
        "version": 1,
        "project": project,
        "epistemic_contract": contract,
        "graph": {"nodes": nodes, "edges": edges},
        "pipelines": [
            {
                "id": "demo-independent-route-election",
                "project_id": PROJECT_ID,
                "name": "Independent Route Election + Verification",
                "definition": {"name": "Independent Route Election + Verification", "nodes": pipeline_nodes, "edges": pipeline_edges},
                "version": 1,
                "created_by": "demo-researcher",
                "created_at": CREATED_AT,
                "updated_at": CREATED_AT,
            }
        ],
        "claims": [],
        "evidence": [],
        "dead_ends": [],
        "literature": [],
        "replay": replay,
    }
    encoded = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return {
        "id": SNAPSHOT_ID,
        "version": 1,
        "integrity_hash": hashlib.sha256(encoded.encode()).hexdigest(),
        "created_at": CREATED_AT,
        "payload": payload,
        "bundled_demo": True,
    }


def bundled_public_snapshot(snapshot_id: str) -> dict[str, Any] | None:
    """Return a defensive copy so request serialization cannot mutate the seed."""

    if snapshot_id != SNAPSHOT_ID:
        return None
    return copy.deepcopy(_snapshot())


def bundled_public_projects() -> list[dict[str, Any]]:
    snapshot = _snapshot()
    project = snapshot["payload"]["project"]
    return [
        {
            **copy.deepcopy(project),
            "snapshot_id": snapshot["id"],
            "bundled_demo": True,
        }
    ]
