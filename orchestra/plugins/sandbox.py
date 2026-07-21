from __future__ import annotations

import os
import resource
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path


class SubprocessSandbox:
    security_boundary = "best_effort_local_subprocess"

    def execute_python(self, source: str, timeout: int = 10, memory_mb: int = 256) -> dict:
        started = time.perf_counter()

        def limits() -> None:
            memory = memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
            resource.setrlimit(resource.RLIMIT_CPU, (timeout, timeout + 1))

        with tempfile.TemporaryDirectory(prefix="orchestra-python-") as directory:
            path = Path(directory) / "experiment.py"
            path.write_text(source)
            env = {"PATH": os.getenv("PATH", ""), "PYTHONHASHSEED": "0", "HOME": directory, "TMPDIR": directory}
            preexec = limits if threading.current_thread() is threading.main_thread() else None
            result = subprocess.run(
                [os.sys.executable, "-I", str(path)],
                cwd=directory,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
                preexec_fn=preexec,
                start_new_session=True,
            )
            artifacts = [p.name for p in Path(directory).iterdir() if p.name != "experiment.py" and p.is_file()]
        return {
            "status": "success" if result.returncode == 0 else "failed",
            "execution_mode": "local",
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
            "artifacts": artifacts,
            "runtime_seconds": round(time.perf_counter() - started, 6),
            "sandbox": self.security_boundary,
            "network_policy": "not guaranteed; use container sandbox in production",
            "memory_policy": "rlimit" if preexec else "not enforced in threaded development execution",
        }


class DockerSandbox:
    security_boundary = "docker_container"

    def __init__(self, image: str = "python:3.13-slim"):
        self.image = image

    def execute_python(self, source: str, timeout: int = 10, memory_mb: int = 256) -> dict:
        if not shutil.which("docker"):
            raise RuntimeError("Docker sandbox is configured but Docker is unavailable")
        started = time.perf_counter()
        command = [
            "docker",
            "run",
            "--rm",
            "--interactive",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--memory",
            f"{memory_mb}m",
            "--memory-swap",
            f"{memory_mb}m",
            "--cpus",
            "1",
            "--pids-limit",
            "64",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=64m",
            "--user",
            "65534:65534",
            self.image,
            "python",
            "-I",
            "-",
        ]
        result = subprocess.run(command, input=source, capture_output=True, text=True, timeout=timeout + 5, env={"PATH": os.getenv("PATH", "")})
        return {
            "status": "success" if result.returncode == 0 else "failed",
            "execution_mode": "local",
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
            "artifacts": [],
            "runtime_seconds": round(time.perf_counter() - started, 6),
            "sandbox": self.security_boundary,
            "network_policy": "disabled",
            "image": self.image,
        }


def configured_sandbox(settings=None):
    if settings is None:
        from orchestra.config import settings

    if settings.sandbox_backend == "docker":
        return DockerSandbox(settings.sandbox_python_image)
    if settings.environment == "production":
        raise RuntimeError("Subprocess sandbox is forbidden in production")
    return SubprocessSandbox()
