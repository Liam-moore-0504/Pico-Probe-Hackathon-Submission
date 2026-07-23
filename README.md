# Pico Probe

> Research you can inspect.

Pico Probe is research software for AI-assisted mathematics. It turns an investigation into a persistent graph of questions, conjectures, evidence, objections, computations, formal checks, discarded routes, and human decisions—not merely a final AI answer.

Built with Codex for OpenAI Build Week 2026.

## Inspiration

Large language models have become remarkably capable mathematical assistants, yet AI-assisted research is still commonly treated as a sequence of independent interactions. A conjecture lives in one chat, a failed proof in another, a symbolic calculation in a notebook, and a counterexample in a script. Even when models and tools are orchestrated successfully, the investigation's memory is often short-lived.

That became especially clear while researching geometric probability and polylogarithms. Models could generate promising conjectures quickly, but one model could make a subtle algebraic mistake and later models could unknowingly inherit it. By the time a symbolic engine or theorem prover was involved, much of the reasoning history—including rejected approaches—had disappeared.

Pico Probe began with questions that ordinary prompt chains do not answer well:

- What promising routes did the models consider and silently discard?
- Why was one proof strategy selected over another?
- Can an abandoned approach be recovered without starting over?
- Which model proposed, modified, or challenged each claim?
- Which assumptions, lemmas, computations, or sources support a conclusion?
- Was a result independently checked, or did several models merely agree?
- Did a symbolic calculation establish the full claim or only one algebraic step?
- Can the complete investigation be replayed in the order it occurred?
- Can another researcher inspect and reuse the method without rerunning everything?
- Can the system preserve failure and state honestly that a question remains unresolved?

Existing tools coordinate execution. **Pico Probe coordinates the evolution of research knowledge.**

Git transformed software development by preserving the history and branching structure of code. Pico Probe applies a similar principle to AI-assisted research: every material claim and research route becomes a durable, inspectable object that can be branched, challenged, verified, replayed, and extended.

Pico Probe complements frameworks such as MCP, LangChain, LeanDojo, SymPy, and Jupyter. Its focus is the persistent research layer above models and tools: the record of how knowledge was generated, disputed, checked, bounded, and accepted.

## What makes Pico Probe different

Pico Probe is not another panel of agents voting on an answer. Model consensus is not treated as verification, fluency is not treated as evidence, and a confidence percentage is not treated as truth.

Its unit of value is the inspectable claim:

1. The researcher defines an **Epistemic Contract** before generation begins.
2. Independent model or human branches propose plans, claims, and possible mechanisms.
3. Unselected routes remain visible as **Negative Knowledge** instead of being deleted.
4. Skeptical branches search for contradictions, counterexamples, and assumption failures.
5. Lean, SymPy, numerical experiments, literature records, plugins, and people contribute distinct forms of evidence.
6. Every execution and graph mutation is retained in **Research Replay**.
7. A **Claim Passport** reports what supports, challenges, verifies, or limits each conclusion.

The final Research Summary is generated from stored graph and assurance records. It does not ask another model to invent a more polished conclusion, and it never upgrades an unverified statement into a proof.

## Research as a computational object

The visual Pipeline Editor compiles a research plan into a versioned dependency graph. Nodes exchange typed `PicoPortMessage` objects rather than unstructured prompt-chain text. Before every node executes, the Research Kernel builds a `NodeExecutionEnvelope` containing the research question, Epistemic Contract, upstream values, downstream contracts, relevant graph context, execution budget, required output schema, and provenance requirements.

```text
Pipeline Editor
      │
      ▼
Assurance-aware Graph Compiler
      │
      ▼
Versioned Execution DAG
      │
      ▼
Scheduler + Human Checkpoints
      │
      ▼
Typed Execution Envelopes
      │
      ▼
AI Models, People, and Plugins
      │
      ▼
Claim Graph + Replay + Passport
```

This preserves explicit dependencies and makes it possible to replace a provider without redesigning the surrounding research method.

## Models and research tools

GPT-5.6 is the featured Build Week route, but Pico Probe is deliberately not locked to one model. The competition edition includes native provider boundaries for:

- OpenAI, including GPT-5.6
- Anthropic
- Google Gemini
- xAI/Grok
- DeepSeek
- local Ollama models
- deployment-approved OpenAI-compatible endpoints

Researchers choose the provider and exact model on each AI node. A pipeline can use one model repeatedly, compare several independent models, use only a local Ollama model, replace an AI step with a human contribution, or combine model reasoning with Lean, SymPy, Monte Carlo, Python experiments, arXiv/Crossref literature lookup, and approved signed plugins.

GPT-5.6 is required for the Build Week project and is demonstrated in the code and validation record. It is **not required for every judge interaction**: the bundled public investigation and Rehearsal mode work without keys, and judges may connect any supported provider they are authorized to use.

## Quick start for judges

Requirements: Docker Desktop.

```bash
docker compose -f docker-compose.demo.yml up --build
```

Open <http://127.0.0.1:8000> and create a local account. No external email or payment setup is needed.

The clean installation automatically includes a privacy-safe immutable showcase in **Public library**:

**Which monomials survive signed multinomial cancellation?**

This published investigation contains the research question, Epistemic Contract, three independent routes, a preserved unexplored branch, an explicit non-affine objection, SymPy evidence, a scoped Lean verification record, the qualified affine conclusion, the saved multi-model pipeline, and a sanitized Research Replay. It is bundled as a signed-content-style snapshot rather than as a personal account database.

### Five-minute credential-free walkthrough

1. Open **Public library** and select the signed-monomial investigation.
2. Inspect its assurance contract, 12-node Claim Graph, saved pipeline, integrity hash, and replay.
3. Return to **Private library** and choose **Start guided investigation**.
4. Follow the animated tutorial as independent routes, an objection, verification records, and a bounded conclusion enter the graph.
5. Open **Epistemic contract** to see the evidence and falsification standard fixed before the run.
6. Open **Pipeline editor** to inspect or change providers, branch connections, merge behavior, plugins, and human checkpoints.
7. Open **Run research**, select **Rehearsal**, and launch the governed pipeline without paid model calls.
8. Inspect **Verification**, **Claim graph**, **Claim passport**, and **Replay**.

Rehearsal is deterministic and visibly labeled. It demonstrates orchestration and assurance behavior without pretending that fixture output came from a live model.

## Configure API keys inside Pico Probe

The recommended judge path is through the interface rather than shell environment variables:

1. Sign in to the local Pico Probe account.
2. Open **Settings & API keys** in the left sidebar.
3. Select `openai`, `anthropic`, `google`, `xai`, or `deepseek`.
4. Paste a provider API key and select **Store securely**.
5. Confirm that **Provider readiness** marks the provider as configured.

The raw key is encrypted before persistence, is never returned by the API, and is excluded from execution envelopes, graph objects, events, replay, and frontend responses. The repository contains no real provider keys.

For local inference, use the separate **Configure local Ollama** panel. Ollama does not accept an API key or device key. See [Ollama setup](docs/OLLAMA_SETUP.md).

## Public and private research libraries

- **Private library** contains the signed-in researcher's editable investigations.
- **Public library** contains immutable snapshots deliberately published by their authors.

A public snapshot captures the project question, assurance contract, Claim Graph, pipelines, claims, evidence, dead ends, literature records, and replay at one version with an integrity hash. Later private edits do not silently rewrite an already published snapshot.

## Architecture

```text
React interface
   │
FastAPI application and domain services
   ├── authentication + encrypted BYOK
   ├── Epistemic Contracts
   ├── typed Claim Graph + Negative Knowledge
   ├── versioned pipeline compiler
   ├── durable DAG scheduler + human checkpoints
   ├── native model-provider boundary
   ├── Lean, SymPy, simulations, literature, plugins
   ├── immutable events + Research Replay
   └── Claim Passport + deterministic Research Summary
          │
    SQLite + in-process demo execution
    PostgreSQL + Redis worker production architecture
```

The competition configuration deliberately uses SQLite and in-process jobs so judges need only Docker. Runtime databases and artifacts are ignored by Git and Docker and are generated cleanly on first launch.

## Verification and epistemic limits

```bash
python -m pytest
python -m ruff check orchestra tests
cd frontend
npm ci
npm run lint
npm run build
```

The current report records 42 backend tests: 41 passing and one optional live-Ollama test skipped when Ollama is unavailable. The repository's configured MyPy CI profile, Docker image, Python 3.13 suite, frontend production build, dependency audits, secret scan, and health endpoint are also validated. See [TEST_REPORT.md](TEST_REPORT.md).

Pico Probe is deliberately precise about what its checks mean:

- Lean success establishes that the submitted formal statement type-checks; it does not establish that the formalization matches the intended real-world claim.
- SymPy validates the submitted symbolic operation, not every surrounding inference.
- Numerical experiments provide reproducible evidence, not deductive proof.
- A Claim Passport is an audit record, not a certificate of truth.
- A guided rehearsal demonstrates the research mechanism; its novelty and literature priority still require scholarly review.

## Repository map

- `frontend/` — competition interface, tutorial, editors, libraries, and settings
- `orchestra/api/` — authenticated and public HTTP API
- `orchestra/kernel/` — scheduling, execution envelopes, prompts, and provider execution
- `orchestra/pipelines/` — graph compiler, typed ports, templates, and validation
- `orchestra/protocol/` — canonical messages, assurance validation, ingestion, and bounded repair
- `orchestra/services/` — research-domain and persistence rules
- `orchestra/plugins/` — Lean, SymPy, Python experiment, Monte Carlo, and signed-plugin support
- `orchestra/demo/` — privacy-safe immutable public showcase data
- `tests/` — API, security, domain, provider, kernel, and submission-flow tests
- `docs/` — architecture, safety, providers, demo, and release evidence

## Competition-edition boundaries

- Public hosting, live payments, production OAuth/SMTP, and public marketplace activation are intentionally outside the private Build Week demo.
- Transactions are disabled in the competition interface.
- Arbitrary unsigned third-party plugin execution is not exposed.

The long-term goal is not to replace researchers. It is to provide a research environment where every idea, computation, proof attempt, counterexample, failed route, verification result, and human decision becomes part of an inspectable and reusable scientific record.
