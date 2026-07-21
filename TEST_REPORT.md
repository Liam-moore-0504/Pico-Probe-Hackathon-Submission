# Pico Probe 3.2 test report — July 21, 2026

The release candidate was checked from the packaged source tree.

- **42 backend tests collected**
- **41 passed**
- **1 optional live Ollama test skipped** because the packaging environment did not expose a running local Ollama service
- Frontend ESLint passed
- Frontend Vite production build passed
- Ruff and the repository's MyPy CI profile passed
- Bandit high-severity scan and Python dependency audit passed
- npm production audit reported zero known vulnerabilities
- Docker demo image built successfully and reached its healthy readiness state
- The complete backend suite also passed inside the Python 3.13 Docker environment with the source mounted read-only

The backend suite covers assurance-aware compilation, named ports, compatible fan-out, conflicting schema rejection, heterogeneous multi-output generation, automatic AI-to-Monte-Carlo-to-interpreter execution, canonical message lineage, multi-upstream joins, assurance binding, artifact persistence, protocol edge direction, counterexample invalidation, local zero-cost semantics, Claim Passport behavior, Ollama configuration/status behavior, and availability/integrity/privacy of the bundled signed-monomial public showcase on a clean database.

Pico Probe 3.2 additionally adds a first-class Ollama settings interface and a safe backend-local start endpoint. A backend inside Docker cannot start an Ollama process on the host; in that arrangement the user starts the Ollama app on macOS or uses the paired local companion.

The project owner confirmed a live GPT-5.6 test with a user-provided API key. No key was retained in this source tree. The automated suite separately verifies the complete BYOK path without a billable request: account registration, encrypted OpenAI credential storage and decryption, compiled `gpt-5.6` live-mode execution through a mocked provider transport, structured output validation, canonical messages, provider events, replay, and absence of the raw key from returned data.
