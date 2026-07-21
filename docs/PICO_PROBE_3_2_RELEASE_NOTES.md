# Pico Probe 3.2 — Provider Setup and Backend Integration Release

## Primary changes

- Added a first-class Ollama configuration card in Settings & Providers.
- Added status, URL configuration, installed-model listing, approved presets, model pull, structured-output test, and save controls.
- Added a safe backend endpoint to start Ollama when the backend is running directly on the same machine and the `ollama` binary is installed.
- Preserved the secure local-companion architecture for Docker/host separation.
- Local Ollama continues to require no API key and reports zero provider cost.
- Research runs remain cancellation-first and have no fixed total duration limit.

## Ollama URLs

- Direct Python backend on macOS: `http://127.0.0.1:11434`
- Backend in Docker on macOS: `http://host.docker.internal:11434`

The backend cannot start a host process from inside an isolated Docker container. In that configuration, launch the Ollama app on the host or use the included local companion.
