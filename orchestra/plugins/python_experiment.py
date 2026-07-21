import hashlib
import platform

from .base import Plugin, PluginManifest
from .sandbox import configured_sandbox


class PythonExperimentPlugin(Plugin):
    manifest: PluginManifest = PluginManifest(
        plugin_id="core.python_experiment",
        name="Sandboxed Python Experiment",
        capabilities=["numerical_test", "python_experiment"],
        permissions=["subprocess:python"],
        filesystem_access="temporary",
        sandbox_required=True,
        input_schema={"type": "object", "required": ["source", "seed"], "properties": {"source": {"type": "string"}, "inputs": {"type": "object"}, "seed": {"type": "integer"}, "timeout": {"type": "integer"}, "dependencies": {"type": "array"}, "expected_artifacts": {"type": "array"}, "expected_metrics": {"type": "array"}, "target_claim_id": {"type": "string"}}},
        output_schema={"type": "object", "required": ["status", "stdout", "stderr", "exit_code", "reproducibility"], "properties": {"status": {"type": "string"}, "stdout": {"type": "string"}, "stderr": {"type": "string"}, "exit_code": {"type": "integer"}, "metrics": {"type": "object"}, "artifacts": {"type": "array"}, "evidence_stance": {"type": "string"}, "reproducibility": {"type": "object"}}},
    )

    def execute(self, payload: dict) -> dict:
        source = payload.get("source", "")
        if not source or len(source) > 100_000:
            raise ValueError("Source must contain 1 to 100,000 characters")
        result = configured_sandbox().execute_python(source, min(int(payload.get("timeout", 10)), 30), min(int(payload.get("memory_mb", 256)), 512))
        result["reproducibility"] = {
            "seed": payload.get("seed"),
            "python": platform.python_version(),
            "source_hash": hashlib.sha256(source.encode()).hexdigest(),
            "declared_inputs": payload.get("inputs", {}),
        }
        result.setdefault("status", "success" if result.get("exit_code") == 0 else "failed")
        result.setdefault("metrics", {})
        result.setdefault("artifacts", [])
        result.setdefault("evidence_stance", "tests")
        return result
