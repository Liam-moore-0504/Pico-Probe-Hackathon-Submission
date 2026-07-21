from __future__ import annotations

import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from .base import Plugin, PluginManifest


class LeanPlugin(Plugin):
    manifest: PluginManifest = PluginManifest(
        plugin_id="core.lean",
        name="Lean 4",
        capabilities=["formal_verification"],
        reliability=0.995,
        permissions=["subprocess:lean"],
        filesystem_access="temporary",
        timeout_seconds=15,
        sandbox_required=True,
        input_schema={"type": "object", "required": ["source"], "properties": {"source": {"type": "string"}, "theorem_name": {"type": "string"}, "target_claim_id": {"type": "string"}, "assumptions": {"type": "array"}, "natural_language_interpretation": {"type": "string"}}},
        output_schema={"type": "object", "required": ["status", "formal_success", "compiler_return_code", "stdout", "stderr", "full_source", "lean_version"], "properties": {"status": {"type": "string"}, "formal_success": {"type": "boolean"}, "compiler_return_code": {"type": "integer"}, "stdout": {"type": "string"}, "stderr": {"type": "string"}, "full_source": {"type": "string"}, "lean_version": {"type": "string"}, "semantic_alignment_warning": {"type": "string"}, "target_claim_id": {"type": "string"}, "artifacts": {"type": "array"}}},
    )

    def execute(self, payload: dict) -> dict:
        code = str(payload.get("source") or payload.get("theorem", ""))
        started = time.perf_counter()
        lean = shutil.which("lean")
        if not lean:
            return {
                "status": "unavailable",
                "execution_mode": "local",
                "verified": False,
                "formal": False,
                "verification_status": "lean_compiler_unavailable",
                "proof_script": code,
                "compiler_output": "",
                "engine": "lean",
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                "formal_success": False, "compiler_return_code": -1, "stdout": "", "stderr": "Lean compiler unavailable", "full_source": code,
                "lean_version": "unavailable", "semantic_alignment_warning": "No formal certificate was produced.", "target_claim_id": payload.get("target_claim_id", ""), "artifacts": [],
            }
        with tempfile.TemporaryDirectory(prefix="orchestra-lean-") as directory:
            source = Path(directory) / "Main.lean"
            source.write_text(code)
            completed = subprocess.run([lean, str(source)], capture_output=True, text=True, timeout=self.manifest.timeout_seconds, env={"PATH": str(Path(lean).parent)})
        verified = completed.returncode == 0
        version = subprocess.run([lean, "--version"], capture_output=True, text=True, timeout=5).stdout.strip()
        return {
            "status": "success" if verified else "failed",
            "execution_mode": "local",
            "verified": verified,
            "formal": True,
            "verification_status": "compiler_verified" if verified else "compiler_rejected",
            "proof_script": code,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "exit_code": completed.returncode,
            "engine": "lean",
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            "formal_success": verified, "compiler_return_code": completed.returncode, "full_source": code,
            "lean_version": version, "semantic_alignment_warning": "Compiler acceptance proves the Lean statement, not automatically its intended natural-language interpretation.",
            "target_claim_id": payload.get("target_claim_id", ""), "artifacts": [],
        }
