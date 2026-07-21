import os

from .base import AnthropicProvider, GeminiProvider, OpenAICompatibleProvider


def ollama_provider():
    base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1")
    return OpenAICompatibleProvider("ollama", base_url, {"127.0.0.1", "localhost", "host.docker.internal", "ollama"}, cloud=False)

PROVIDERS = {
    "openai": lambda: OpenAICompatibleProvider("openai", "https://api.openai.com/v1", {"api.openai.com"}),
    "anthropic": AnthropicProvider,
    "google": GeminiProvider,
    "deepseek": lambda: OpenAICompatibleProvider("deepseek", "https://api.deepseek.com", {"api.deepseek.com"}),
    "xai": lambda: OpenAICompatibleProvider("xai", "https://api.x.ai/v1", {"api.x.ai"}),
    "ollama": ollama_provider,
}

PROVIDER_METADATA = {
    "openai": {"supports_streaming": True, "supports_structured_output": True, "local": False},
    "anthropic": {"supports_streaming": True, "supports_structured_output": True, "local": False},
    "google": {"supports_streaming": True, "supports_structured_output": True, "local": False},
    "deepseek": {"supports_streaming": True, "supports_structured_output": True, "local": False},
    "xai": {"supports_streaming": True, "supports_structured_output": True, "local": False},
    "ollama": {"supports_streaming": True, "supports_structured_output": True, "local": True},
    "generic": {"supports_streaming": True, "supports_structured_output": True, "local": False},
    "mock": {"supports_streaming": False, "supports_structured_output": True, "local": True},
}
