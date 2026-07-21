# OpenAI Build Week submission copy

## Project name

Pico Probe

## Tagline

Research you can inspect.

## One-sentence pitch

Pico Probe turns GPT‑5.6 research from an opaque report into an auditable Claim Graph where evidence, falsification, deterministic verification, model provenance, and human authority remain explicitly separate.

## Inspiration

AI research tools can search broadly and write convincingly, but their output often collapses several very different things into one answer: model inference, source evidence, disagreement, formal proof, computation, and researcher judgment. This makes a polished report difficult to audit and easy to over-trust. Pico Probe was built around a stricter question: what would the interface look like if it were never allowed to hide those distinctions?

## What it does

Before a run, the researcher accepts an Epistemic Contract defining the evidence standard, falsification criteria, source requirements, independent checks, and human checkpoints. GPT‑5.6 can then propose structured claims and conduct an adversarial critique. Sources, counterexamples, Lean proofs, SymPy computations, experiments, and human decisions enter a persistent typed graph with provenance. At the end, Pico Probe produces a Claim Passport showing what supports each claim, what challenges it, what was checked independently, and what remains unresolved. Research Replay preserves the complete event sequence.

## How it was built

The product uses a React interface, FastAPI domain services, a persistent typed Research Graph, immutable events, a versioned DAG scheduler, human checkpoints, structured provider adapters, and deterministic Lean/SymPy plugins. SQLite and in-process jobs provide a reproducible judge demo; the preserved launch architecture supports PostgreSQL and Redis workers. GPT‑5.6 is configured as the proposal and falsification model. Codex was used throughout repository inspection, implementation, testing, refactoring, UI development, and submission preparation.

## Why it is different

Pico Probe is not another panel of agents voting on an answer. Agreement between models is not treated as verification. Its unit of value is the inspectable claim: explicit assumptions, provenance, support, opposition, independent checks, human authority, and known limitations.

## Challenges

The central challenge was preserving epistemic distinctions through every layer. A provider response had to become typed research objects without allowing repair or parsing to masquerade as validation. Long-running work needed replayable checkpoints and cancellation. Formal verification needed precise language about scope: a Lean success establishes that a submitted formal statement type-checks, not that the formalization matches the world.

## Accomplishments

- Researcher-authored Epistemic Contracts
- Persistent Claim Graph with typed evidence and contradiction
- GPT‑5.6 proposal/falsification topology
- Human-controlled pipeline steps
- Independent Lean and SymPy verification
- arXiv and DOI source resolution
- Immutable Research Replay
- Printable Claim Passports
- Deterministic no-key rehearsal mode
- Guided first investigation

## What is next

After the competition: public deployment at `picoprobe.com`, institutional collaboration, richer source-excerpt alignment, reproducible artifact bundles, controlled plugin execution, and domain-specific assurance profiles.

## Suggested screenshots

1. Landing page in light mode
2. Landing page in dark mode
3. Guided Claim Graph
4. Epistemic Contract
5. GPT‑5.6 assurance pipeline
6. Lean verification result
7. Claim Passport
8. Research Replay
