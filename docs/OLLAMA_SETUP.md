# Local Ollama setup

Pico Probe uses Ollama locally and does not require an Ollama API key or device token. Local model calls are marked `local`, record token usage, and have a provider cost of zero.

## Fast path with Docker Desktop

1. Install and open the official Ollama application.
2. Pull a reviewed model:

   ```bash
   ollama pull llama3.1:8b
   ```

3. Confirm that Ollama responds:

   ```bash
   curl http://127.0.0.1:11434/api/version
   ```

4. Start Pico Probe:

   ```bash
   docker compose -f docker-compose.demo.yml up --build
   ```

5. In Pico Probe, open **Settings → Providers → Ollama**, use `http://host.docker.internal:11434`, select `llama3.1:8b`, save, then choose **Test**.

Use `http://127.0.0.1:11434` when Pico Probe itself runs directly on the Mac. The backend accepts only unauthenticated HTTP loopback/private endpoints on port 11434. It never falls back to rehearsal mode when Ollama is unavailable.

## Optional local companion

The companion is a narrow loopback-only helper that can detect/start Ollama, list models, pull reviewed presets, and run a structured test. It exposes no arbitrary shell or filesystem operation.

```bash
python -m desktop.pico_probe_companion.app
```

The terminal prints a one-time pairing token. The service binds to `127.0.0.1:43117`, requires that token, accepts only configured web origins, and can stop only an Ollama process that it started itself. Model downloads require an approved preset and an explicit user action.

## Live verification

The optional test never runs unless explicitly enabled:

```bash
OLLAMA_LIVE_BASE_URL=http://host.docker.internal:11434 \
OLLAMA_LIVE_MODEL=llama3.1:8b \
pytest -m ollama_live
```

It performs the settings structured-output test and then runs an Ollama generator into the Monte Carlo plugin through canonical port messages with no manual rewriting.

## Troubleshooting

- **Invalid or expired token:** remove the Ollama entry from API Keys. Ollama local mode takes no key; configure its URL and model in the Ollama provider panel.
- **Unavailable from Docker:** use `host.docker.internal`, not `127.0.0.1`, because loopback inside the container points to the container.
- **Model missing:** run `ollama list`, then pull one of the reviewed presets shown by Pico Probe.
- **Test fails honestly:** start Ollama, confirm `/api/version`, confirm the model name exactly, and select **Test** again. No result labeled live/local is synthesized when the service fails.


## Long-running research and cancellation

Pico Probe does not impose a total research-run duration limit. A run may remain active for days, pause at human checkpoints, and resume from persisted state. Local Ollama generation uses a bounded connection timeout but no fixed read deadline by default. The Stop action requests cancellation; streamed local generation checks that request between chunks.

Deterministic code, Lean, and sandbox plugins still use resource limits because unrestricted generated code is unsafe. Long computations should be checkpointed or divided into resumable batches rather than executed as an unlimited subprocess. To impose an explicit Ollama node deadline, set `hard_timeout_seconds` on that node.
