from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal

from pydantic import BaseModel, Field


class PluginManifest(BaseModel):
    plugin_id: str = Field(pattern=r"^[a-z0-9_.-]+$")
    name: str
    version: str = "1.0.0"
    author: str = "Pico Probe"
    category: str = "research_tool"
    capabilities: list[str] = Field(default_factory=list)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    reliability: float = Field(default=0.5, ge=0, le=1)
    dependencies: list[str] = Field(default_factory=list)
    runtime_requirements: list[str] = Field(default_factory=list)
    cost_model: str = "local"
    permissions: list[str] = Field(default_factory=list)
    network_domains: list[str] = Field(default_factory=list)
    filesystem_access: Literal["none", "temporary", "read", "write"] = "none"
    timeout_seconds: int = Field(default=30, ge=1, le=600)
    memory_mb: int = Field(default=256, ge=32, le=4096)
    sandbox_required: bool = False
    checksum: str | None = None
    installation_source: str = "bundled"
    entrypoint: str = "plugin.py"
    signature_algorithm: Literal["ed25519"] | None = None
    publisher_public_key: str | None = None
    signature: str | None = None


class Plugin(BaseModel, ABC):
    manifest: PluginManifest

    @abstractmethod
    def execute(self, payload: dict) -> dict: ...
