"""Proveedores en la nube (demostrativos): cualquier API compatible con OpenAI, y Anthropic.

Ambos usan Server-Sent Events para el streaming; solo cambia el formato de cada evento.
"""

import json
from collections.abc import AsyncIterator

import httpx

from ..config import settings
from .base import LLMError, LLMProvider


async def _sse_data(resp: httpx.Response) -> AsyncIterator[str]:
    async for line in resp.aiter_lines():
        if line.startswith("data:"):
            data = line[5:].strip()
            if data and data != "[DONE]":
                yield data


class _RemoteProvider(LLMProvider):
    api_key: str = ""

    async def prepare(self) -> None:
        if not self.api_key:
            self.status.set("error", f"Falta la API key para {self.name} (revisa .env)")
        elif not self.model:
            self.status.set("error", f"Falta el nombre del modelo para {self.name} (revisa .env)")
        else:
            self.status.set("ready", "Listo")

    async def _post_stream(self, base_url: str, path: str, headers: dict, payload: dict) -> AsyncIterator[str]:
        try:
            async with self.client(base_url, settings.llm_timeout, headers) as c:
                async with c.stream("POST", path, json=payload) as resp:
                    if resp.status_code != 200:
                        body = (await resp.aread()).decode(errors="replace")
                        raise LLMError(f"{self.name} respondió {resp.status_code}: {body[:300]}")
                    async for data in _sse_data(resp):
                        yield data
        except httpx.HTTPError as exc:
            raise LLMError(f"No se pudo conectar con {self.name}: {exc}") from exc


class OpenAICompatibleProvider(_RemoteProvider):
    """OpenAI, Groq, OpenRouter, Together, Mistral, vLLM, LM Studio… (POST /chat/completions)."""

    name = "openai"

    def __init__(self, **kw):
        super().__init__(settings.openai_model, **kw)
        self.api_key = settings.openai_api_key
        self.base_url = settings.openai_base_url.rstrip("/")

    async def stream(self, system: str, user: str) -> AsyncIterator[str]:
        payload = {
            "model": self.model,
            "stream": True,
            "temperature": settings.llm_temperature,
            "max_tokens": settings.llm_max_tokens,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async for data in self._post_stream(self.base_url, "/chat/completions", headers, payload):
            choices = json.loads(data).get("choices") or [{}]
            if token := (choices[0].get("delta") or {}).get("content"):
                yield token


class AnthropicProvider(_RemoteProvider):
    """Claude vía Messages API (POST /v1/messages)."""

    name = "anthropic"

    def __init__(self, **kw):
        super().__init__(settings.anthropic_model, **kw)
        self.api_key = settings.anthropic_api_key
        self.base_url = settings.anthropic_base_url.rstrip("/")

    async def stream(self, system: str, user: str) -> AsyncIterator[str]:
        payload = {
            "model": self.model,
            "stream": True,
            "max_tokens": settings.llm_max_tokens,
            "temperature": settings.llm_temperature,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        headers = {"x-api-key": self.api_key, "anthropic-version": "2023-06-01"}
        async for data in self._post_stream(self.base_url, "/v1/messages", headers, payload):
            event = json.loads(data)
            if event.get("type") == "error":
                raise LLMError(event.get("error", {}).get("message", "Error de Anthropic"))
            if event.get("type") == "content_block_delta":
                if token := event.get("delta", {}).get("text"):
                    yield token
