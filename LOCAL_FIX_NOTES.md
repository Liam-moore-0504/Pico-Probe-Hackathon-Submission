# Local Fix Notes

This copy fixes the Python packaging metadata so `python -m pip install -e .` no longer fails because of flat-layout package discovery.

Important local commands:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -e .
python -m pytest -q
python -m uvicorn orchestra.api.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Ollama direct backend:

```bash
ollama serve
ollama pull llama3.1:8b
curl http://127.0.0.1:11434/api/version
```

Use `http://127.0.0.1:11434` when running the backend directly. Use `http://host.docker.internal:11434` when the backend is inside Docker Desktop.
