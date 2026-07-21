from __future__ import annotations

import shutil
import subprocess
import time

from orchestra.providers.ollama_manager import (
    APPROVED_MODELS,
)
from orchestra.providers.ollama_manager import (
    OllamaManager as HttpOllamaManager,
)


class CompanionOllamaManager(HttpOllamaManager):
    def __init__(self):
        super().__init__("http://127.0.0.1:11434")
        self._process: subprocess.Popen | None = None

    def binary_path(self) -> str | None:
        return shutil.which("ollama")

    def local_status(self) -> dict:
        status = self.status()
        status["binary_found"] = bool(self.binary_path())
        return status

    def start(self) -> dict:
        if self.status()["reachable"]:
            return self.local_status()
        binary = self.binary_path()
        if not binary:
            raise RuntimeError("Ollama is not installed. Open https://ollama.com/download to install it.")
        self._process = subprocess.Popen([binary, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.time() + 15
        while time.time() < deadline:
            if self.status()["reachable"]:
                return self.local_status()
            time.sleep(0.4)
        raise RuntimeError("Ollama did not become reachable within 15 seconds")

    def stop(self) -> dict:
        if self._process and self._process.poll() is None:
            self._process.terminate()
            self._process.wait(timeout=5)
        self._process = None
        return self.local_status()

    def pull_local(self, model: str) -> dict:
        if model not in APPROVED_MODELS:
            raise ValueError("Model is not approved")
        binary = self.binary_path()
        if not binary:
            raise RuntimeError("Ollama is not installed")
        completed = subprocess.run([binary, "pull", model], capture_output=True, text=True, timeout=3600)
        if completed.returncode:
            raise RuntimeError("Ollama model pull failed")
        return {"model": model, "status": "success"}
