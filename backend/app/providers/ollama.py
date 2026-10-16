"""Proveedor local con Ollama.

`run()` es un supervisor que vive mientras vive la app:

    ┌──────────────── ensure_ready() ────────────────┐      ┌──── _watch() ────┐
    │ intento n: servidor? → ¿modelo? → pull →       │ ok   │ cada 60 s:       │
    │            verificar (/api/tags + /api/show) → │ ───▶ │ ¿sigue el modelo?│
    │            precalentar                         │      │ ¿responde Ollama?│
    │ fallo → estado "error"/"starting" + backoff    │ ◀─── │ no → volver      │
    │         5 s, 10 s, 20 s … 60 s (o "Reintentar")│      └──────────────────┘
    └────────────────────────────────────────────────┘

Así, si la descarga de qwen se corta, queda a medias o alguien borra el volumen, la app
avisa (estado + intento + próximo reintento en /api/health) y vuelve a intentarlo sola.
Ollama reanuda las capas ya descargadas, así que cada reintento continúa donde quedó.
"""

import json
import logging
import time
from collections.abc import AsyncIterator

import httpx

from ..config import settings
from .base import LLMError, LLMProvider

log = logging.getLogger("pseudo2code.ollama")


class ServerUnavailable(LLMError):
    """Ollama todavía no responde (normal durante los primeros segundos del arranque)."""


def _describe(exc: Exception) -> str:
    text = str(exc).strip()
    return text if text else type(exc).__name__


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, model: str | None = None, *, url: str | None = None, **kw):
        super().__init__(model or settings.ollama_model, **kw)
        self.url = url or settings.ollama_url

    # ------------------------------------------------------------- supervisor
    async def run(self) -> None:
        while True:
            await self.ensure_ready()
            await self._watch()

    async def ensure_ready(self) -> None:
        """Reintenta prepare() con backoff exponencial hasta que el modelo esté listo."""
        delay = settings.ollama_retry_min_seconds
        while True:
            self.status.attempt += 1
            self.status.next_retry_at = None
            attempt = self.status.attempt
            try:
                await self.prepare()
                log.info("Modelo %s listo (intento %d)", self.model, attempt)
                self.status.set("ready", "Listo")
                return
            except (LLMError, httpx.HTTPError, json.JSONDecodeError) as exc:
                reason = _describe(exc)
                state = "starting" if isinstance(exc, ServerUnavailable) else "error"
                self.status.last_error = reason
                self.status.next_retry_at = time.time() + delay
                self.status.set(state, f"{self.model} aún no está disponible: {reason}")
                log.warning("Intento %d fallido para %s: %s. Reintento en %.0f s",
                            self.status.attempt, self.model, reason, delay)
            woke = await self._sleep_or_wake(delay)
            delay = settings.ollama_retry_min_seconds if woke else min(delay * 2, settings.ollama_retry_max_seconds)

    async def _watch(self) -> None:
        """Ya listo: comprueba periódicamente que el modelo siga disponible."""
        while True:
            await self._sleep_or_wake(settings.ollama_watchdog_seconds)
            try:
                if await self._model_present():
                    continue
                log.warning("El modelo %s ya no está en Ollama; se volverá a descargar", self.model)
                self.status.set("starting", f"{self.model} desapareció de Ollama; preparando de nuevo…")
            except (httpx.HTTPError, json.JSONDecodeError) as exc:
                log.warning("Se perdió la conexión con Ollama: %s", _describe(exc))
                self.status.set("starting", "Se perdió la conexión con Ollama; reintentando…")
            return

    # ------------------------------------------------------------ un intento
    async def prepare(self) -> None:
        """Un intento completo. Lanza LLMError si algo falla (el supervisor reintenta)."""
        await self._check_server()
        if not await self._model_present():
            if not settings.ollama_auto_pull:
                raise LLMError(f"el modelo no está descargado (OLLAMA_AUTO_PULL=false). "
                               f"Ejecuta: docker compose exec ollama ollama pull {self.model}")
            await self._pull()
        await self._verify()
        await self._warm_up()
        self.status.set("ready", "Listo")

    async def _check_server(self) -> None:
        self.status.set("starting", "Conectando con Ollama…")
        try:
            async with self.client(self.url, 5.0) as c:
                (await c.get("/api/version")).raise_for_status()
        except httpx.HTTPError as exc:
            raise ServerUnavailable(f"Ollama no responde en {self.url}") from exc

    async def _model_present(self) -> bool:
        async with self.client(self.url, 10.0) as c:
            resp = await c.get("/api/tags")
            resp.raise_for_status()
        names = {m["name"] for m in resp.json().get("models", [])}
        return self.model in names or f"{self.model}:latest" in names

    async def _pull(self) -> None:
        log.info("Descargando %s…", self.model)
        self.status.set("pulling", f"Descargando {self.model}…", 0.0)
        totals: dict[str, tuple[int, int]] = {}
        success = False
        # El timeout de lectura actúa como detector de descargas "colgadas".
        async with self.client(self.url, settings.ollama_pull_stall_seconds) as c:
            async with c.stream("POST", "/api/pull", json={"model": self.model, "stream": True}) as resp:
                if resp.status_code != 200:
                    raise LLMError(f"no se pudo descargar: HTTP {resp.status_code}")
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    ev = json.loads(line)
                    if "error" in ev:
                        raise LLMError(f"error de descarga: {ev['error']}")
                    if ev.get("status") == "success":
                        success = True
                    if ev.get("digest") and ev.get("total"):
                        totals[ev["digest"]] = (ev.get("completed", 0), ev["total"])
                    done = sum(c for c, _ in totals.values())
                    total = sum(t for _, t in totals.values()) or 1
                    self.status.set("pulling", f"Descargando {self.model}…", round(100 * done / total, 1))
        if not success:
            raise LLMError("la descarga se interrumpió antes de terminar")

    async def _verify(self) -> None:
        """Confirma que Ollama registró el modelo completo antes de declararlo listo."""
        self.status.set("loading", f"Verificando {self.model}…")
        if not await self._model_present():
            raise LLMError("la descarga terminó pero el modelo no aparece en Ollama")
        async with self.client(self.url, 30.0) as c:
            resp = await c.post("/api/show", json={"model": self.model})
        if resp.status_code != 200:
            raise LLMError(f"el modelo está incompleto o dañado (/api/show → {resp.status_code})")

    async def _warm_up(self) -> None:
        """Carga el modelo en RAM para que la primera conversión no sea lenta (prompt vacío)."""
        self.status.set("loading", f"Cargando {self.model} en memoria…")
        async with self.client(self.url, settings.llm_timeout) as c:
            resp = await c.post(
                "/api/generate",
                json={"model": self.model, "stream": False, "keep_alive": settings.ollama_keep_alive,
                      "options": {"num_ctx": settings.ollama_num_ctx}},
            )
            if resp.status_code != 200:
                raise LLMError(f"no se pudo cargar en memoria: {resp.text[:200]}")

    # ------------------------------------------------------------- generación
    async def stream(self, system: str, user: str) -> AsyncIterator[str]:
        payload = {
            "model": self.model,
            "stream": True,
            "keep_alive": settings.ollama_keep_alive,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "options": {
                "temperature": settings.llm_temperature,
                "num_ctx": settings.ollama_num_ctx,
                "num_predict": settings.llm_max_tokens,
            },
        }
        try:
            async with self.client(self.url, settings.llm_timeout) as c:
                async with c.stream("POST", "/api/chat", json=payload) as resp:
                    if resp.status_code == 404:
                        # El modelo desapareció (p. ej. borraron el volumen): avisar al supervisor.
                        self.status.set("starting", f"{self.model} no está disponible; preparando de nuevo…")
                        self.request_retry()
                        raise LLMError(f"El modelo {self.model} no está disponible todavía; se está descargando.")
                    if resp.status_code != 200:
                        body = (await resp.aread()).decode(errors="replace")
                        raise LLMError(f"Ollama respondió {resp.status_code}: {body[:300]}")
                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        chunk = json.loads(line)
                        if "error" in chunk:
                            raise LLMError(chunk["error"])
                        if token := chunk.get("message", {}).get("content", ""):
                            yield token
                        if chunk.get("done"):
                            break
        except httpx.HTTPError as exc:
            self.request_retry()  # que el supervisor compruebe si Ollama sigue vivo
            raise LLMError(f"No se pudo conectar con Ollama en {self.url}: {exc}") from exc
