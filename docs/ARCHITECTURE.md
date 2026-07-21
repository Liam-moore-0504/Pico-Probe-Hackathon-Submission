# Architecture

## Assurance-first compilation

Pico Probe does not execute visual-editor JSON directly. `PipelineCompiler` parses the definition, hydrates plugin and model interfaces, validates the DAG, binds a versioned Assurance Contract, checks named-port schemas and mappings, derives downstream expectations and node-specific assurance rules, estimates cost, and persists a `CompiledPipeline`.

Every scheduler step receives a secret-free `NodeExecutionEnvelope` containing the research question, frozen contract, node role, canonical input messages, all incoming edges and upstream values, resolved named inputs, every downstream consumer and schema, scoped claims/evidence/dead ends/literature/events, every output-port contract, budget, and provenance requirements. The plugin boundary receives this same envelope metadata while bundled plugin code receives only its schema-validated payload.

Every edge value is persisted as a `PicoPortMessage` with a stable ID, schema ID, exact port, producer, source message IDs, Assurance Contract version, and kernel-issued artifact references. `InputResolver` rejects missing inputs, malformed values, incompatible mappings, and ambiguous joins while preserving every legal fan-in message. The compiler validates structural schema assignability, supports compatible fan-out, creates distinct typed ports for heterogeneous fan-out, and rejects conflicting contracts unless an explicit adapter is inserted.

`ResearchPromptAssembler` creates structured provider messages containing all downstream contracts. `OutputValidator` validates all ports, JSON shape/ranges/enums, assurance rules, object dependencies, false verification/tool/artifact claims, and downstream completeness. Rehearsal fixtures are deterministic. A malformed live/local provider response receives at most one secret-free same-provider repair call; both the invalid original and accepted replacement are artifacts, repair provenance is explicit, and a second invalid response fails the node before a plugin can see it.

Protocol dependencies use dependency → dependent direction. Evidence attaches atomically to target claims. Discovery operates only over the authorized project and scopes novelty language to indexed records.

Pico Probe treats the persistent Research Graph and immutable event stream as the product. FastAPI validates transport data, services enforce authorization and domain rules, repositories own persistence, and the database boundary supports SQLite locally and PostgreSQL in production.

Alembic owns production schema deployment. PostgreSQL stores authoritative graph, epistemic, billing, account, collaboration, marketplace, artifact metadata, and job state. Redis provides distributed job dispatch and request-rate counters. Workers atomically claim durable jobs, execute independent DAG levels concurrently, persist checkpoints, honor cancellation/pause/human gates, and recover stale queued work.

Provider execution resolves BYOK before platform credentials. Async native adapters emit started/completed/failed events, persist usage and provenance, validate typed research objects, and reserve/settle credits only for platform-funded calls. Plugins cannot access persistence. Bundled tools run through the kernel; approved third-party packages require Ed25519 signatures and execute only through the configured container sandbox.

Ollama uses the same OpenAI-compatible provider boundary without credentials. Per-user settings allow only loopback/private HTTP endpoints on port 11434. Health, model discovery, structured tests, and allowlisted model pulls are honest about availability. The optional companion binds only to loopback, uses an in-memory pairing secret and origin allowlist, and exposes no general command or file API.

Publishing allowlist-builds immutable snapshots. Collaboration preserves branch-specific nodes, edges, claims, evidence, and conflict decisions. Benchmarks derive measurements from persisted runs rather than accepting model-authored scores.
