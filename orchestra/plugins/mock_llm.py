from .base import Plugin, PluginManifest


class MockLLMPlugin(Plugin):
    manifest: PluginManifest = PluginManifest(
        plugin_id="core.mock_llm",
        name="Test-only Mock Model",
        category="test",
        capabilities=["hypothesis_generation", "critique", "synthesis", "counterexample_search"],
        reliability=0.5,
        cost_model="mock",
    )

    def execute(self, payload):
        return {
            "status": "success",
            "execution_mode": "mock",
            "provider": "mock",
            "model": "deterministic-test-model",
            "mock": True,
            "output": "MOCK OUTPUT: " + str(payload.get("prompt", "")),
            "usage": {"input_tokens": 0, "output_tokens": 0},
        }
