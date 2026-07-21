import json
from pathlib import Path


def templates() -> list[dict]:
    values = json.loads((Path(__file__).parent / "templates.json").read_text())
    existing = {item["id"] for item in values}
    additions = [
        ("geometric-probability", "Geometric Probability Investigation", "Experimental Designer"),
        ("literature-contradictions", "Scientific Literature Contradiction Scan", "Literature Researcher"),
        ("research-gap-discovery", "Research Gap Discovery", "Opportunity Detector"),
        ("cross-disciplinary-transfer", "Cross-Disciplinary Transfer Search", "Scientific Researcher"),
        ("replication-study", "Replication Study", "Reproducibility Reviewer"),
    ]
    for template_id, name, role in additions:
        if template_id in existing:
            continue
        values.append(
            {
                "id": template_id, "name": name, "version": 1,
                "assurance_recommendations": ["independent check", "counterexample search", "final human approval"],
                "mock_fixture": "successful_research_route",
                "nodes": [
                    {"id": "formalize", "type": "formalization", "role": "Formalizer", "config": {"provider": "openai", "model": "gpt-5.6", "label": "Formalize question"}},
                    {"id": "investigate", "type": "hypothesis_generation", "role": role, "config": {"provider": "openai", "model": "gpt-5.6", "label": name}},
                    {"id": "skeptic", "type": "counterexample_search", "role": "Skeptic", "config": {"provider": "openai", "model": "gpt-5.6", "label": "Adversarial check"}},
                    {"id": "human", "type": "human_review", "role": "Methodological Reviewer", "config": {"human_input": True, "label": "Researcher decision"}},
                ],
                "edges": [
                    {"source": "formalize", "target": "investigate", "relation": "produces"},
                    {"source": "investigate", "target": "skeptic", "relation": "challenges"},
                    {"source": "skeptic", "target": "human", "relation": "requires_approval"},
                ],
            }
        )
    return values
