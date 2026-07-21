# Assurance Contracts

An Assurance Contract is the frozen standard against which a Pico Probe run is compiled and judged. A run binds one immutable contract version and SHA-256 hash before any node executes. The binding is available at `GET /runs/{id}/assurance-status` and in Research Replay.

Contracts govern evidence, falsification, sources, verification, reproducibility, uncertainty, publication, forbidden shortcuts, independent checks, counterexample search, experiment size, contradictions, and final human authority.

Create and activate versions with `POST /projects/{id}/assurance-contracts`, `GET /projects/{id}/assurance-contracts`, and `POST /projects/{id}/assurance-contracts/{contract_id}/activate`.

For a no-key rehearsal, the run request may explicitly set `use_default_contract: true`. Compilation otherwise rejects a project without an active contract.

The compiler derives node rules. Hypothesis generators expose assumptions and falsification conditions; experiments require a seed; literature nodes require sources; synthesis cannot self-certify; tool nodes preserve raw outputs; and formal verification is only successful when the actual compiler accepts the source.
