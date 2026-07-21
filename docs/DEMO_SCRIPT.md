# Pico Probe Build Week demo script

Target length: 2 minutes 45 seconds. Keep the final public YouTube video under three minutes.

## Before recording

- Start `docker compose -f docker-compose.demo.yml up --build`.
- Create the local demo account.
- In **Settings & API keys**, store the OpenAI key and confirm provider readiness before recording. Never display or paste the key on camera.
- Prepare an OpenAI-only pipeline whose AI nodes use `gpt-5.6`, plus an adversarial step and human checkpoint.
- Complete a short live run once before recording so model latency does not surprise you.
- Do not describe Rehearsal output as live provider output.

## 0:00–0:18 — The problem

“AI research systems can produce convincing reports, but the report often hides which statements came from a model, which evidence supports them, which routes failed, and whether anything was independently checked. Pico Probe makes the investigation itself inspectable.”

Show the Pico Probe home screen.

## 0:18–0:42 — Published research record

Open **Public library**, select **Which monomials survive signed multinomial cancellation?**, and scroll through the snapshot.

“This clean installation includes an immutable research snapshot: the question, assurance contract, competing and discarded routes, Claim Graph, verification records, saved pipeline, integrity hash, and replay. The qualified affine conclusion remains separate from the unresolved non-affine boundary.”

## 0:42–1:05 — Contract and pipeline

Open the guided project, then **Epistemic contract** and **Pipeline editor**.

“Before generation, the researcher fixes the evidence standard, falsification criteria, independent checks, and human authority. The pipeline can use GPT-5.6, other cloud models, local Ollama, people, Lean, SymPy, simulations, or approved plugins. Providers are replaceable; the research contract and graph remain stable.”

## 1:05–1:35 — Live GPT-5.6 governed run

Open **Run research**, select the prepared pipeline and **AI-led — live providers with human gates**, then launch it. Show the completed live run or its final stages and briefly show the researcher checkpoint.

“Here GPT-5.6 produces typed output through an encrypted user-provided key. A separate step tries to break the claim, output is checked against the compiled schema, and the pipeline stops wherever the Epistemic Contract requires a person. Provider, model, usage, lineage, and assurance events remain attached to the run.”

## 1:35–1:55 — Independent verification

Open **Verification** and show a successful scoped Lean or SymPy result.

“Pico Probe never asks a language model to certify its own work. Lean establishes that the submitted formal statement type-checks; SymPy establishes the submitted symbolic operation. Pico Probe records their exact scope instead of calling either one universal proof.”

## 1:55–2:20 — Passport and replay

Open **Claim passport**, then **Replay**.

“The result is not a confidence score. The passport exposes assumptions, support, opposition, independent checks, provenance, human decisions, and unresolved limitations. Replay reconstructs how the research changed rather than showing only the final prose.”

## 2:20–2:37 — How Codex was used

“Codex helped transform an early multi-model pipeline into this integrated system. It mapped the inherited backend, implemented and connected the typed compiler, execution envelopes, provider and verification paths, React workflows, regression tests, Docker packaging, and submission hardening. I retained the mathematical-integrity rules, product direction, autonomy model, and final design decisions.”

## 2:37–2:45 — Close

“Existing tools coordinate execution. Pico Probe coordinates the evolution of research knowledge—including what failed, what was checked, and what remains unknown.”
