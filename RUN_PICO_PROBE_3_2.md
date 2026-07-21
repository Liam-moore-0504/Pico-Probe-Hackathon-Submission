# Run Pico Probe 3.2

## Fastest demo

```bash
docker compose -f docker-compose.demo.yml up --build
```

Open `http://127.0.0.1:8000`.

## Local Ollama on macOS

1. Install and open the Ollama app.
2. Pull a model:

```bash
ollama pull llama3.1:8b
```

3. Confirm it is running:

```bash
curl http://127.0.0.1:11434/api/version
```

4. In Pico Probe open **Settings & Providers → Configure local Ollama**.
5. If Pico Probe is in Docker, set `http://host.docker.internal:11434`.
6. If the backend is running directly on the Mac, set `http://127.0.0.1:11434`.
7. Click **Check**, choose the installed model, **Save**, and **Test model**.

The **Start local service** button works only when the Pico Probe backend itself runs on the same machine and can find the `ollama` binary. Docker cannot directly launch a host process.

## Direct development

Backend:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m uvicorn orchestra.api.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```
