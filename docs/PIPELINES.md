# Pipeline guide

## Typed compilation

Nodes may declare named `interface.input_ports` and `interface.output_ports`. Each port carries a schema ID, JSON Schema, required flag, multiple-input flag, and description. Legacy pipelines are upgraded during compilation. Edges declare `source_port`, `target_port`, `relation`, and optional JSON-path `mapping`.

Save the pipeline and call `POST /pipelines/{id}/compile`. Compilation errors block execution. The editor shows schemas, assurance rules, and immediate downstream consumers.

An AI node directly preceding a plugin inherits the plugin's exact input contract. The model is instructed to emit executable structured input, and the resolver passes it to the plugin without manual prompt rewriting. Multi-source ports must explicitly accept multiple values; otherwise the join is rejected.

Ten editable versioned templates live in `orchestra/pipelines/templates.json`. Validation detects duplicate IDs/edges, cycles, missing endpoints, self-edges, unreachable nodes, missing/disabled plugins, unsupported providers, absent credentials, generic endpoint omissions, elevated plugin permissions, invalid retry policies, undeclared branch joins, and declared maximum cost.

Workers execute topological levels concurrently and persist every step. Node configuration supports plugins/providers, models, prompts/messages, typed output schemas, temperature, token/cost caps, retry/backoff policy, branch behavior, and human review. Human gates set the run to `waiting_for_user`; `/runs/{run_id}/human-input` records the decision and resumes from the checkpoint without repeating completed nodes.
