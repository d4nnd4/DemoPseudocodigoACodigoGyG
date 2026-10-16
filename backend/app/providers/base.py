"""Contrato común para cualquier proveedor de LLM.

Para conectar un modelo nuevo basta con heredar de `LLMProvider`, implementar
`stream()` (y opcionalmente `prepare()`), y registrarlo en `providers/__init__.py`.
"""

import asyncio
import re
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import asdict, dataclass

import httpx


class LLMError(RuntimeError):
    pass


@dataclass
class ProviderStatus:
    # starting -> (pulling) -> loading -> ready   |   error (se reintenta solo)
    state: str = "starting"
    detail: str = "Conectando con el proveedor…"
    progress: float | None = None  # 0-100 durante la descarga del modelo
    attempt: int = 0               # intentos de preparación desde el último "ready"
    last_error: str | None = None
    next_retry_at: float | None = None  # epoch (s) del próximo reintento automático

    def set(self, state: str, detail: str, progress: float | None = None) -> None:
        self.state, self.detail, self.progress = state, detail, progress
        if state == "ready":
            self.attempt, self.last_error, self.next_retry_at = 0, None, None

    def as_dict(self) -> dict:
        data = asdict(self)
        data["retry_in"] = max(0, round(self.next_retry_at - time.time())) if self.next_retry_at else None
        return data


class LLMProvider(ABC):
    name: str = "base"

    def __init__(self, model: str, *, transport: httpx.AsyncBaseTransport | None = None):
        self.model = model
        self.status = ProviderStatus()
        self._transport = transport  # inyectable en tests
        self._wake: asyncio.Event | None = None  # "reintentar ahora" / "revisa el modelo"
        self._retry_pending = False

    @property
    def ready(self) -> bool:
        return self.status.state == "ready"

    def client(self, base_url: str, timeout: float, headers: dict | None = None) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(timeout, connect=10.0),
            headers=headers,
            transport=self._transport,
        )

    async def prepare(self) -> None:
        """Deja el proveedor listo para generar (descargas, warm-up…)."""
        self.status.set("ready", "Listo")

    async def run(self) -> None:
        """Tarea de fondo durante toda la vida de la app. Por defecto solo prepara una vez;
        Ollama la sobreescribe con un supervisor que reintenta y vigila el modelo."""
        await self.prepare()

    def request_retry(self) -> None:
        """Despierta al supervisor: corta la espera del backoff o fuerza una revisión.
        Llamar desde el event loop (endpoints `async def`)."""
        self._retry_pending = True
        if self._wake is not None:
            self._wake.set()

    async def _sleep_or_wake(self, seconds: float) -> bool:
        """Duerme `seconds` o hasta que llamen a request_retry(). True si lo despertaron."""
        self._wake = asyncio.Event()  # se crea en el loop actual
        if not self._retry_pending:
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=seconds)
            except asyncio.TimeoutError:
                return False
        self._retry_pending = False
        return True

    @abstractmethod
    def stream(self, system: str, user: str) -> AsyncIterator[str]:
        """Emite el texto generado por fragmentos."""

    def info(self) -> dict:
        return {"provider": self.name, "model": self.model, **self.status.as_dict()}


FENCE_RE = re.compile(r"```[\w+#.-]*\s*\n(.*?)(?:```|$)", re.DOTALL)


def clean_code(raw: str) -> str:
    """Quita fences de markdown y texto sobrante si el modelo no siguió las reglas."""
    text = raw.strip()
    match = FENCE_RE.search(text)
    if match:
        text = match.group(1)
    return text.strip("\n") + "\n"
