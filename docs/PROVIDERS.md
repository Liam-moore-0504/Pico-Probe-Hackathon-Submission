# Provider adapter guide

Native async adapters are implemented for OpenAI, Anthropic, Gemini, DeepSeek, xAI/Grok, and Ollama. Generic OpenAI-compatible services are supported only through `ORCHESTRA_GENERIC_PROVIDER_ENDPOINTS`, a deployment-owned JSON allowlist; users cannot supply arbitrary endpoints.

Credential resolution is `user BYOK → platform key → unavailable`. BYOK calls record usage but do not consume Orchestra provider credits. Platform-key calls require an active reviewed pricing rule, quota capacity, and sufficient prepaid balance before execution.

Pipeline provider configuration supports `provider`, `model`, `messages` or `prompt`, `temperature`, `max_tokens`, `structured_schema`, `require_typed_output`, and—for generic adapters—`endpoint_id`. Cloud endpoints require HTTPS and a fixed hostname allowlist. Provider errors returned to clients never contain API keys or raw upstream bodies.

Live validation requires the corresponding credentials; no adapter silently substitutes mock output. Mock runs are deterministic and explicitly labeled `mock`.

Ollama is the exception to cloud credential handling: it intentionally accepts no API key. Each user can save a reviewed local/private endpoint and explicit default model. Status, model listing, structured test, and confirmed preset-pull endpoints are exposed under `/providers/ollama/*`. Ollama calls traverse the same secret-free node envelope, structured prompt, output validation, canonical-message persistence, artifact, lineage, and repair path as cloud OpenAI-compatible calls; their execution mode is `local` and provider cost is zero. See [OLLAMA_SETUP.md](OLLAMA_SETUP.md).
