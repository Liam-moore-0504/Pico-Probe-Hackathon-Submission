"""Safe local/private-network Ollama discovery and management."""

from __future__ import annotations

import ipaddress
import shutil
import subprocess
import time
from urllib.parse import urlparse

import httpx

APPROVED_MODELS = {"qwen3:8b", "llama3.1:8b", "deepseek-r1:8b", "qwen3:4b"}
LOCAL_NAMES = {"localhost", "127.0.0.1", "::1", "host.docker.internal", "ollama"}


def validate_ollama_url(value: str) -> str:
    parsed = urlparse(value.rstrip("/"))
    if parsed.scheme != "http" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Ollama URL must be an unauthenticated HTTP local/private endpoint")
    allowed = parsed.hostname in LOCAL_NAMES
    if not allowed:
        try:
            allowed = ipaddress.ip_address(parsed.hostname).is_private or ipaddress.ip_address(parsed.hostname).is_loopback
        except ValueError:
            allowed = False
    if not allowed:
        raise ValueError("Ollama URL must resolve to localhost or an explicitly private address")
    if parsed.port not in {None, 11434}:
        raise ValueError("Ollama endpoint must use port 11434")
    return value.rstrip("/").removesuffix("/v1")


class OllamaManager:
    def __init__(self, base_url: str):
        self.base_url = validate_ollama_url(base_url)

    def status(self, recommended_model: str | None = None) -> dict:
        try:
            response = httpx.get(self.base_url + "/api/tags", timeout=3)
            response.raise_for_status()
            models = sorted({item.get("name") or item.get("model") for item in response.json().get("models", []) if item.get("name") or item.get("model")})
            version = None
            try:
                version_response = httpx.get(self.base_url + "/api/version", timeout=2)
                if version_response.is_success:
                    version = version_response.json().get("version")
            except httpx.HTTPError:
                pass
            return {"installed": True, "running": True, "reachable": True, "base_url": self.base_url, "openai_compatible_url": self.base_url + "/v1", "version": version, "models": models, "recommended_model_installed": bool(recommended_model and recommended_model in models)}
        except Exception:
            return {"installed": False, "running": False, "reachable": False, "base_url": self.base_url, "openai_compatible_url": self.base_url + "/v1", "version": None, "models": [], "recommended_model_installed": False}


    def local_binary_status(self) -> dict:
        binary = shutil.which("ollama")
        version = None
        if binary:
            try:
                result = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=5)
                version = (result.stdout or result.stderr).strip() or None
            except Exception:
                version = None
        return {"binary_found": bool(binary), "binary_path": binary, "binary_version": version}

    def start_local(self) -> dict:
        current = self.status()
        if current["reachable"]:
            return {**current, **self.local_binary_status(), "started": False, "message": "Ollama is already running"}
        binary = shutil.which("ollama")
        if not binary:
            raise RuntimeError("Ollama is not installed on the machine running the Pico Probe backend")
        subprocess.Popen([binary, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        deadline = time.time() + 20
        while time.time() < deadline:
            current = self.status()
            if current["reachable"]:
                return {**current, **self.local_binary_status(), "started": True, "message": "Ollama started"}
            time.sleep(0.5)
        raise RuntimeError("Ollama was launched but did not become reachable within 20 seconds")

    def pull(self, model: str) -> dict:
        if model not in APPROVED_MODELS:
            raise ValueError("Model is not in Pico Probe's reviewed local preset list")
        response = httpx.post(self.base_url + "/api/pull", json={"model": model, "stream": False}, timeout=3600)
        response.raise_for_status()
        return {"model": model, "status": response.json().get("status", "success")}

    def structured_test(self, model: str) -> dict:
        if not model:
            raise ValueError("Select an installed Ollama model")
        response = httpx.post(
            self.base_url + "/v1/chat/completions",
            json={"model": model, "messages": [{"role": "system", "content": "Return JSON only."}, {"role": "user", "content": 'Return exactly {"status":"ok","integer":3}'}], "temperature": 0, "response_format": {"type": "json_object"}},
            timeout=60,
        )
        response.raise_for_status()
        body = response.json()
        return {"success": True, "model": model, "request_id": body.get("id"), "content": body["choices"][0]["message"]["content"], "usage": body.get("usage", {}), "cost_micros": 0, "execution_mode": "local"}
