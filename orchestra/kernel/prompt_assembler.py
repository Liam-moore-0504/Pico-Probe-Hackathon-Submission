"""Structured provider messages derived from a node execution envelope."""

from __future__ import annotations

from orchestra.kernel.execution_envelope import NodeExecutionEnvelope
from orchestra.repositories.repository import dumps


class ResearchPromptAssembler:
    def assemble(self, envelope: NodeExecutionEnvelope) -> list[dict[str, str]]:
        system = (
            "You execute one node inside Pico Probe, an auditable research system; you are not producing a standalone chat answer. "
            "Use the supplied research question and every relevant upstream object. Obey the frozen Assurance Contract. "
            "Produce data for the declared downstream consumers. Preserve assumptions and provenance. Never claim tool execution "
            "without supplied tool provenance and never self-certify a claim you generated. Return only output conforming to the required JSON schema."
        )
        kernel = {
            "node": {"id": envelope.pipeline_node_id, "type": envelope.node_type, "role": envelope.node_role, "goal": envelope.node_goal},
            "assurance_contract": envelope.epistemic_contract,
            "node_assurance_requirements": envelope.node_assurance_requirements,
            "input_messages": [item.model_dump(mode="json") for item in envelope.inputs],
            "resolved_inputs": envelope.resolved_inputs,
            "downstream_consumers": [item.model_dump(mode="json") for item in envelope.downstream],
            "output_contract": {"schema_id": envelope.required_output_type, "json_schema": envelope.required_output_schema, "ports": {name: {"schema_id": envelope.output_port_schema_ids.get(name), "json_schema": schema} for name, schema in envelope.output_port_contracts.items()}},
            "budget": envelope.budget.model_dump(mode="json"),
            "provenance_requirements": envelope.provenance_requirements,
        }
        research = {"research_question": envelope.research_question, "task": envelope.node_instructions, "relevant_memory": envelope.context.model_dump(mode="json")}
        return [
            {"role": "system", "content": system},
            {"role": "developer", "content": "PICO PROBE KERNEL ENVELOPE (secret-free):\n" + dumps(kernel)},
            {"role": "user", "content": dumps(research)},
        ]
