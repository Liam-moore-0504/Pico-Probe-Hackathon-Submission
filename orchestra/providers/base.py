"""Normalized provider contract and HTTP adapters."""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, Field


class ProviderRequest(BaseModel):
    model: str
    messages: list[dict[str, str]]
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_tokens: int = Field(default=2048, ge=1, le=200_000)
    structured_schema: dict[str, Any] | None = None
    timeout_seconds: float | None = Field(default=120, ge=1, le=86_400)
    idempotency_key: str | None = None


def _httpx_timeout(request: ProviderRequest) -> httpx.Timeout:
    """Use a bounded connection timeout but permit cancellation-driven local generation.

    `timeout_seconds=None` intentionally disables read/write/pool deadlines while
    retaining a 10-second connection deadline. Long-running research remains
    cancellable through streamed provider execution.
    """
    if request.timeout_seconds is None:
        return httpx.Timeout(None, connect=10.0)
    return httpx.Timeout(request.timeout_seconds, connect=min(10.0, request.timeout_seconds))


class ProviderResponse(BaseModel):
    provider: str
    model: str
    execution_mode: str = "live"
    request_id: str | None = None
    content: str
    usage: dict[str, int] = Field(default_factory=dict)
    latency_ms: float


class ProviderStreamChunk(BaseModel):
    content: str = ""
    usage: dict[str, int] = Field(default_factory=dict)
    request_id: str | None = None
    done: bool = False


class ProviderError(RuntimeError):
    pass


class Provider(ABC):
    name: str
    cloud: bool = True
    supports_streaming: bool = False
    supports_structured_output: bool = False

    @abstractmethod
    def execute(self, request: ProviderRequest, api_key: str | None) -> ProviderResponse: ...

    @abstractmethod
    async def aexecute(self, request: ProviderRequest, api_key: str | None) -> ProviderResponse: ...

    async def astream(self, request: ProviderRequest, api_key: str | None) -> AsyncIterator[ProviderStreamChunk]:
        response = await self.aexecute(request, api_key)
        yield ProviderStreamChunk(content=response.content, usage=response.usage, request_id=response.request_id, done=True)

    def health(self, api_key: str | None = None) -> dict:
        return {"health": "unknown", "models": []}


class OpenAICompatibleProvider(Provider):
    def __init__(self, name: str, base_url: str, allowed_hosts: set[str], cloud: bool = True):
        parsed = urlparse(base_url)
        if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.hostname not in allowed_hosts:
            raise ValueError("Provider endpoint is not allowlisted")
        if cloud and parsed.scheme != "https":
            raise ValueError("Cloud provider endpoints require HTTPS")
        self.name, self.base_url, self.cloud = name, base_url.rstrip("/"), cloud
        self.supports_streaming = True
        self.supports_structured_output = True

    def execute(self, request: ProviderRequest, api_key: str | None) -> ProviderResponse:
        if self.cloud and not api_key:
            raise ProviderError(f"{self.name} is not configured")
        started = time.perf_counter()
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        if request.idempotency_key:
            headers["Idempotency-Key"] = request.idempotency_key
        try:
            response = httpx.post(self.base_url + "/chat/completions", headers=headers, json=self._body(request), timeout=_httpx_timeout(request))
            response.raise_for_status()
            body = response.json()
            return ProviderResponse(
                provider=self.name,
                model=request.model,
                execution_mode="live" if self.cloud else "local",
                request_id=response.headers.get("x-request-id") or body.get("id"),
                content=body["choices"][0]["message"]["content"],
                usage=body.get("usage", {}),
                latency_ms=(time.perf_counter() - started) * 1000,
            )
        except Exception as exc:
            raise ProviderError(f"{self.name} request failed; see server logs with the request correlation ID") from exc

    async def aexecute(self, request: ProviderRequest, api_key: str | None) -> ProviderResponse:
        if self.cloud and not api_key:
            raise ProviderError(f"{self.name} is not configured")
        started = time.perf_counter()
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        if request.idempotency_key:
            headers["Idempotency-Key"] = request.idempotency_key
        try:
            async with httpx.AsyncClient(timeout=_httpx_timeout(request)) as client:
                response = await client.post(self.base_url + "/chat/completions", headers=headers, json=self._body(request))
            response.raise_for_status()
            body = response.json()
            return ProviderResponse(
                provider=self.name,
                model=request.model,
                execution_mode="live" if self.cloud else "local",
                request_id=response.headers.get("x-request-id") or body.get("id"),
                content=body["choices"][0]["message"]["content"],
                usage=body.get("usage", {}),
                latency_ms=(time.perf_counter() - started) * 1000,
            )
        except httpx.HTTPError as exc:
            raise ProviderError(f"{self.name} request failed; see server logs with the request correlation ID") from exc

    @staticmethod
    def _body(request: ProviderRequest) -> dict:
        body = request.model_dump(include={"model", "messages", "temperature", "max_tokens"})
        if request.structured_schema:
            body["response_format"] = {"type": "json_schema", "json_schema": {"name": "research_objects", "strict": True, "schema": request.structured_schema}}
        return body

    def health(self, api_key: str | None = None) -> dict:
        if self.cloud and not api_key:
            return {"health": "unconfigured", "models": []}
        try:
            response = httpx.get(self.base_url + "/models", headers={"Authorization": f"Bearer {api_key}"} if api_key else {}, timeout=10)
            response.raise_for_status()
            models = sorted(str(item["id"]) for item in response.json().get("data", []) if item.get("id"))[:100]
            return {"health": "available", "models": models}
        except Exception:
            return {"health": "unavailable", "models": []}

    async def astream(self, request: ProviderRequest, api_key: str | None) -> AsyncIterator[ProviderStreamChunk]:
        if self.cloud and not api_key:
            raise ProviderError(f"{self.name} is not configured")
        body = {**self._body(request), "stream": True, "stream_options": {"include_usage": True}}
        try:
            async with httpx.AsyncClient(timeout=_httpx_timeout(request)) as client:
                headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
                if request.idempotency_key:
                    headers["Idempotency-Key"] = request.idempotency_key
                async with client.stream("POST", self.base_url + "/chat/completions", headers=headers, json=body) as response:
                    response.raise_for_status()
                    request_id = response.headers.get("x-request-id")
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        payload = line.removeprefix("data:").strip()
                        if payload == "[DONE]":
                            yield ProviderStreamChunk(request_id=request_id, done=True)
                            break
                        data = json.loads(payload)
                        content = ((data.get("choices") or [{}])[0].get("delta") or {}).get("content") or ""
                        yield ProviderStreamChunk(content=content, usage=data.get("usage") or {}, request_id=request_id or data.get("id"))
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise ProviderError(f"{self.name} streaming request failed; see server logs with the request correlation ID") from exc


class AnthropicProvider(Provider):
    name = "anthropic"
    supports_streaming = True
    supports_structured_output = True

    def execute(self, request: ProviderRequest, api_key: str | None) -> ProviderResponse:
        if not api_key:
            raise ProviderError("anthropic is not configured")
        started = time.perf_counter()
        system = "\n".join(item["content"] for item in request.messages if item.get("role") == "system")
        messages = [item for item in request.messages if item.get("role") != "system"]
        body = {"model": request.model, "messages": messages, "max_tokens": request.max_tokens, "temperature": request.temperature}
        if system:
            body["system"] = system
        if request.structured_schema:
            body.update({"tools": [{"name": "emit_research_objects", "description": "Return the requested structured research objects", "input_schema": request.structured_schema}], "tool_choice": {"type": "tool", "name": "emit_research_objects"}})
        try:
            headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
            if request.idempotency_key:
                headers["Idempotency-Key"] = request.idempotency_key
            response = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=body,
                timeout=_httpx_timeout(request),
            )
            response.raise_for_status()
            data = response.json()
            text = self._content(data)
            usage = data.get("usage", {})
            return ProviderResponse(
                provider=self.name,
                model=request.model,
                request_id=response.headers.get("request-id") or data.get("id"),
                content=text,
                usage={"input_tokens": usage.get("input_tokens", 0), "output_tokens": usage.get("output_tokens", 0)},
                latency_ms=(time.perf_counter() - started) * 1000,
            )
        except Exception as exc:
            raise ProviderError("anthropic request failed; see server logs with the request correlation ID") from exc

    async def aexecute(self, request: ProviderRequest, api_key: str | None) -> ProviderResponse:
        if not api_key:
            raise ProviderError("anthropic is not configured")
        started = time.perf_counter()
        system = "\n".join(item["content"] for item in request.messages if item.get("role") == "system")
        messages = [item for item in request.messages if item.get("role") != "system"]
        body = {"model": request.model, "messages": messages, "max_tokens": request.max_tokens, "temperature": request.temperature}
        if system:
            body["system"] = system
        if request.structured_schema:
            body.update({"tools": [{"name": "emit_research_objects", "description": "Return the requested structured research objects", "input_schema": request.structured_schema}], "tool_choice": {"type": "tool", "name": "emit_research_objects"}})
        try:
            headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
            if request.idempotency_key:
                headers["Idempotency-Key"] = request.idempotency_key
            async with httpx.AsyncClient(timeout=_httpx_timeout(request)) as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=headers,
                    json=body,
                )
            response.raise_for_status()
            data = response.json()
            text = self._content(data)
            usage = data.get("usage", {})
            return ProviderResponse(
                provider=self.name,
                model=request.model,
                request_id=response.headers.get("request-id") or data.get("id"),
                content=text,
                usage={"input_tokens": usage.get("input_tokens", 0), "output_tokens": usage.get("output_tokens", 0)},
                latency_ms=(time.perf_counter() - started) * 1000,
            )
        except httpx.HTTPError as exc:
            raise ProviderError("anthropic request failed; see server logs with the request correlation ID") from exc

    @staticmethod
    def _content(data: dict) -> str:
        tool = next((part for part in data.get("content", []) if part.get("type") == "tool_use" and part.get("name") == "emit_research_objects"), None)
        if tool:
            return json.dumps(tool.get("input", {}), separators=(",", ":"))
        return "".join(part.get("text", "") for part in data.get("content", []) if part.get("type") == "text")

    def health(self, api_key: str | None = None) -> dict:
        if not api_key:
            return {"health": "unconfigured", "models": []}
        try:
            response = httpx.get("https://api.anthropic.com/v1/models", headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"}, timeout=10)
            response.raise_for_status()
            return {"health": "available", "models": sorted(item["id"] for item in response.json().get("data", []) if item.get("id"))[:100]}
        except Exception:
            return {"health": "unavailable", "models": []}

    async def astream(self, request: ProviderRequest, api_key: str | None) -> AsyncIterator[ProviderStreamChunk]:
        if not api_key:
            raise ProviderError("anthropic is not configured")
        system = "\n".join(item["content"] for item in request.messages if item.get("role") == "system")
        body = {"model": request.model, "messages": [item for item in request.messages if item.get("role") != "system"], "max_tokens": request.max_tokens, "temperature": request.temperature, "stream": True}
        if system:
            body["system"] = system
        if request.structured_schema:
            body.update({"tools": [{"name": "emit_research_objects", "description": "Return the requested structured research objects", "input_schema": request.structured_schema}], "tool_choice": {"type": "tool", "name": "emit_research_objects"}})
        try:
            async with httpx.AsyncClient(timeout=_httpx_timeout(request)) as client:
                headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
                if request.idempotency_key:
                    headers["Idempotency-Key"] = request.idempotency_key
                async with client.stream("POST", "https://api.anthropic.com/v1/messages", headers=headers, json=body) as response:
                    response.raise_for_status()
                    request_id = response.headers.get("request-id")
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = json.loads(line.removeprefix("data:").strip())
                        event_type = data.get("type")
                        if event_type == "content_block_delta":
                            delta = data.get("delta", {})
                            yield ProviderStreamChunk(content=delta.get("text") or delta.get("partial_json") or "", request_id=request_id)
                        elif event_type == "message_start":
                            yield ProviderStreamChunk(usage={"input_tokens": data.get("message", {}).get("usage", {}).get("input_tokens", 0)}, request_id=request_id)
                        elif event_type == "message_delta":
                            yield ProviderStreamChunk(usage={"output_tokens": data.get("usage", {}).get("output_tokens", 0)}, request_id=request_id)
                        elif event_type == "message_stop":
                            yield ProviderStreamChunk(request_id=request_id, done=True)
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise ProviderError("anthropic streaming request failed; see server logs with the request correlation ID") from exc


class GeminiProvider(Provider):
    name = "google"
    supports_streaming = True
    supports_structured_output = True

    def execute(self, request: ProviderRequest, api_key: str | None) -> ProviderResponse:
        if not api_key:
            raise ProviderError("google is not configured")
        started = time.perf_counter()
        contents = [
            {"role": "model" if item.get("role") == "assistant" else "user", "parts": [{"text": item["content"]}]} for item in request.messages if item.get("role") != "system"
        ]
        body: dict = {"contents": contents, "generationConfig": {"temperature": request.temperature, "maxOutputTokens": request.max_tokens}}
        if request.structured_schema:
            body["generationConfig"].update({"responseMimeType": "application/json", "responseJsonSchema": request.structured_schema})
        try:
            response = httpx.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{request.model}:generateContent",
                headers={"x-goog-api-key": api_key},
                json=body,
                timeout=_httpx_timeout(request),
            )
            response.raise_for_status()
            data = response.json()
            content = data["candidates"][0]["content"]["parts"][0]["text"]
            usage = data.get("usageMetadata", {})
            return ProviderResponse(
                provider=self.name,
                model=request.model,
                request_id=response.headers.get("x-request-id"),
                content=content,
                usage={"input_tokens": usage.get("promptTokenCount", 0), "output_tokens": usage.get("candidatesTokenCount", 0)},
                latency_ms=(time.perf_counter() - started) * 1000,
            )
        except Exception as exc:
            raise ProviderError("google request failed; see server logs with the request correlation ID") from exc

    async def aexecute(self, request: ProviderRequest, api_key: str | None) -> ProviderResponse:
        if not api_key:
            raise ProviderError("google is not configured")
        started = time.perf_counter()
        contents = [
            {"role": "model" if item.get("role") == "assistant" else "user", "parts": [{"text": item["content"]}]}
            for item in request.messages
            if item.get("role") != "system"
        ]
        body: dict = {"contents": contents, "generationConfig": {"temperature": request.temperature, "maxOutputTokens": request.max_tokens}}
        if request.structured_schema:
            body["generationConfig"].update({"responseMimeType": "application/json", "responseJsonSchema": request.structured_schema})
        try:
            async with httpx.AsyncClient(timeout=_httpx_timeout(request)) as client:
                response = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{request.model}:generateContent",
                    headers={"x-goog-api-key": api_key},
                    json=body,
                )
            response.raise_for_status()
            data = response.json()
            content = data["candidates"][0]["content"]["parts"][0]["text"]
            usage = data.get("usageMetadata", {})
            return ProviderResponse(
                provider=self.name,
                model=request.model,
                request_id=response.headers.get("x-request-id"),
                content=content,
                usage={"input_tokens": usage.get("promptTokenCount", 0), "output_tokens": usage.get("candidatesTokenCount", 0)},
                latency_ms=(time.perf_counter() - started) * 1000,
            )
        except httpx.HTTPError as exc:
            raise ProviderError("google request failed; see server logs with the request correlation ID") from exc

    def health(self, api_key: str | None = None) -> dict:
        if not api_key:
            return {"health": "unconfigured", "models": []}
        try:
            response = httpx.get("https://generativelanguage.googleapis.com/v1beta/models", headers={"x-goog-api-key": api_key}, timeout=10)
            response.raise_for_status()
            models = sorted(item["name"].removeprefix("models/") for item in response.json().get("models", []) if item.get("name"))[:100]
            return {"health": "available", "models": models}
        except Exception:
            return {"health": "unavailable", "models": []}

    async def astream(self, request: ProviderRequest, api_key: str | None) -> AsyncIterator[ProviderStreamChunk]:
        if not api_key:
            raise ProviderError("google is not configured")
        contents = [{"role": "model" if item.get("role") == "assistant" else "user", "parts": [{"text": item["content"]}]} for item in request.messages if item.get("role") != "system"]
        body: dict = {"contents": contents, "generationConfig": {"temperature": request.temperature, "maxOutputTokens": request.max_tokens}}
        if request.structured_schema:
            body["generationConfig"].update({"responseMimeType": "application/json", "responseJsonSchema": request.structured_schema})
        try:
            async with httpx.AsyncClient(timeout=_httpx_timeout(request)) as client:
                async with client.stream("POST", f"https://generativelanguage.googleapis.com/v1beta/models/{request.model}:streamGenerateContent?alt=sse", headers={"x-goog-api-key": api_key}, json=body) as response:
                    response.raise_for_status()
                    request_id = response.headers.get("x-request-id")
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = json.loads(line.removeprefix("data:").strip())
                        parts = (((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or [])
                        content = "".join(part.get("text", "") for part in parts)
                        usage = data.get("usageMetadata", {})
                        yield ProviderStreamChunk(content=content, usage={"input_tokens": usage.get("promptTokenCount", 0), "output_tokens": usage.get("candidatesTokenCount", 0)}, request_id=request_id)
                    yield ProviderStreamChunk(request_id=request_id, done=True)
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise ProviderError("google streaming request failed; see server logs with the request correlation ID") from exc
