# Pico Probe Build Week activation status

The private Build Week submission does not require public hosting, payments, OAuth, SMTP, cloud secrets, or a production domain. Those capabilities remain preserved in the separate `PicoProbe_Public_Launch_Foundation` folder.

## Submission logistics remaining

- [x] Record one real local Ollama run through the compiled execution envelope. `llama3.1:8b` completed the generator → canonical message → Monte Carlo path on July 20, 2026 with zero provider cost.
- [x] Test the repository from a fresh clone using `docker-compose.demo.yml`.
- [x] Run the final backend, frontend, dependency, secret, and Docker health checks.
- [x] Create the private GitHub repository.
- [ ] Record the demo video using `docs/DEMO_SCRIPT.md`.
- [ ] Grant the repository access required by the official Devpost rules.
- [ ] Upload the final description, screenshots, video, and repository link to Devpost.

## Non-blocking future validation

- Record an intentionally malformed real-provider response exercising the repair branch. The same-provider live/local repair path, artifact preservation, rejection behavior, and structured validation are implemented and covered deterministically; the successful live Ollama run did not naturally emit malformed output.
- Add broader browser-driven automation for every editor and Discovery action. Backend contract tests and frontend lint/build pass, and the Ollama settings interface is wired to status/configure/start/pull/test endpoints.

## Intentionally postponed

- Public AWS/Render deployment and `picoprobe.com`
- Stripe, production OAuth, SMTP, and legal launch documents
- Public marketplace and arbitrary third-party plugin execution
- Production load, backup/restore, incident response, and multi-region validation

## Implemented in the 3.0 compiler upgrade

- Typed nodes, named ports, schema-aware edges, mappings, and compatibility checks
- Versioned Assurance Contracts and immutable run bindings
- Compiled pipelines and canonical Node Execution Envelopes
- Scoped graph/dead-end/literature context and downstream expectations
- Lossless multi-upstream resolution and ambiguous-join rejection
- Structured provider prompts and strict downstream output validation
- Deterministic rehearsal repair, artifact persistence, and assurance events
- Standardized SymPy, Python experiment, Monte Carlo, and Lean contracts
- Correct protocol dependency direction and evidence-to-claim linking
- Reviewable strategy planning, executable templates, and grounded Discovery opportunities
- Pipeline compilation and Discovery UI views
- Stable persisted `PicoPortMessage` values on compiled edges, with message lineage and query API
- Structurally checked compatible fan-out, heterogeneous multi-output generation, and strict multi-upstream joins
- Port-by-port range/enum/assurance validation and one-attempt same-provider live/local repair
- Ollama status, configuration, models, structured test and confirmed preset-pull APIs
- Optional paired loopback companion for safe Ollama start/stop and reviewed model pulls
- A real local `llama3.1:8b` generator → Monte Carlo integration run

## Remaining engineering depth after the RC

- Literature remains service-based rather than a port-standardized bundled plugin.
- Counterexamples recursively invalidate recorded dependent claims and recommend reruns; automatic selective rerun scheduling remains future depth.
- Large results are stored as artifacts, while compact copies remain in run-step JSON for UI inspection.
- API routes remain concentrated in `orchestra/api/app.py`; router extraction remains code-quality debt.
- The optional local companion has a backend contract and secure localhost CLI, but no signed native installer. The main Settings page now provides direct Ollama status/configure/start/pull/test controls; host-process start remains unavailable from inside Docker by design.
