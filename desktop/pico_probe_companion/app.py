"""Narrow localhost API; intentionally exposes no arbitrary command or file access."""

from __future__ import annotations

import hashlib
import os
import secrets

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel

from .ollama_manager import CompanionOllamaManager

app = FastAPI(title="Pico Probe Local Companion", version="1.0")
allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "PICO_PROBE_COMPANION_ORIGINS",
        "http://127.0.0.1:8000,http://localhost:8000",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Pico-Pairing"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])
manager = CompanionOllamaManager()
pairing_token = secrets.token_urlsafe(32)
paired_hash: str | None = None


class PairRequest(BaseModel):
    token: str


class ModelRequest(BaseModel):
    model: str


def authorize(value: str | None) -> None:
    if not paired_hash or not value or not secrets.compare_digest(hashlib.sha256(value.encode()).hexdigest(), paired_hash):
        raise HTTPException(401, "Companion pairing is required")


@app.get("/health")
def health():
    return {"status": "ok", "bind": "127.0.0.1", "pairing_required": paired_hash is None}


@app.post("/pair")
def pair(data: PairRequest):
    global paired_hash
    if not secrets.compare_digest(data.token, pairing_token):
        raise HTTPException(401, "Invalid pairing token")
    paired_hash = hashlib.sha256(data.token.encode()).hexdigest()
    return {"paired": True}


@app.get("/ollama/status")
def status(x_pico_pairing: str | None = Header(None)):
    authorize(x_pico_pairing)
    return manager.local_status()


@app.post("/ollama/start")
def start(x_pico_pairing: str | None = Header(None)):
    authorize(x_pico_pairing)
    return manager.start()


@app.post("/ollama/stop")
def stop(x_pico_pairing: str | None = Header(None)):
    authorize(x_pico_pairing)
    return manager.stop()


@app.get("/ollama/models")
def models(x_pico_pairing: str | None = Header(None)):
    authorize(x_pico_pairing)
    return manager.local_status()["models"]


@app.post("/ollama/pull")
def pull(data: ModelRequest, x_pico_pairing: str | None = Header(None)):
    authorize(x_pico_pairing)
    return manager.pull_local(data.model)


@app.post("/ollama/test")
def test(data: ModelRequest, x_pico_pairing: str | None = Header(None)):
    authorize(x_pico_pairing)
    return manager.structured_test(data.model)


def main() -> None:
    import uvicorn

    print(f"Pico Probe companion pairing token: {pairing_token}")
    uvicorn.run(app, host="127.0.0.1", port=43117, log_level="info")


if __name__ == "__main__":
    main()
