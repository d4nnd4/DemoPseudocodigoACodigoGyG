"""Espacio reservado para conectar OTRO modelo (ver docs/OTRO_MODELO.md).

Antes de escribir código, revisa si tu modelo ya encaja en un proveedor existente:
  * Se sirve con Ollama           -> LLM_PROVIDER=ollama   + OLLAMA_MODEL=<nombre>
  * Expone /v1/chat/completions   -> LLM_PROVIDER=openai   + OPENAI_BASE_URL (vLLM, LM Studio,
                                     llama.cpp server, TGI, Groq, OpenRouter, Azure…)
  * Es Claude                     -> LLM_PROVIDER=anthropic

Si no encaja, implementa aquí `stream()` y actívalo con LLM_PROVIDER=custom.
La plantilla asume un servicio HTTP propio que responde NDJSON {"token": "..."} por línea;
cámbialo por el formato real de tu API.
"""

import json
from collections.abc import AsyncIterator

import httpx

from ..config import settings
from .base import LLMError, LLMProvider


class CustomProvider(LLMProvider):
    name = "custom"

    def __init__(self, **kw):
        super().__init__(settings.custom_model or "sin-configurar", **kw)
        self.base_url = settings.custom_base_url.rstrip("/")
        self.api_key = settings.custom_api_key

    async def prepare(self) -> None:
        # Aquí podrías: comprobar que el servicio responde, descargar pesos, precalentar…
        if not self.base_url:
            self.status.set("error", "Proveedor custom sin configurar: define CUSTOM_BASE_URL en .env "
                                     "(ver docs/OTRO_MODELO.md)")
            return
        self.status.set("ready", "Listo")

    async def stream(self, system: str, user: str) -> AsyncIterator[str]:
        # TODO: adapta el payload y el parseo al formato de tu API.
        payload = {"model": self.model, "system": system, "prompt": user,
                   "temperature": settings.llm_temperature, "max_tokens": settings.llm_max_tokens}
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else None
        try:
            async with self.client(self.base_url, settings.llm_timeout, headers) as c:
                async with c.stream("POST", "/generate", json=payload) as resp:
                    if resp.status_code != 200:
                        body = (await resp.aread()).decode(errors="replace")
                        raise LLMError(f"custom respondió {resp.status_code}: {body[:300]}")
                    async for line in resp.aiter_lines():
                        if line.strip() and (token := json.loads(line).get("token")):
                            yield token
        except httpx.HTTPError as exc:
            raise LLMError(f"No se pudo conectar con {self.base_url}: {exc}") from exc
