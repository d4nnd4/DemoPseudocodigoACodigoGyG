"""Registro de proveedores. Se elige con la variable de entorno LLM_PROVIDER."""

from ..config import settings
from .base import LLMError, LLMProvider, clean_code
from .custom import CustomProvider
from .ollama import OllamaProvider
from .remote import AnthropicProvider, OpenAICompatibleProvider

PROVIDERS: dict[str, type[LLMProvider]] = {
    "ollama": OllamaProvider,
    "openai": OpenAICompatibleProvider,
    "anthropic": AnthropicProvider,
    "custom": CustomProvider,   # <- espacio para otro modelo (providers/custom.py)
}


def build_provider(name: str | None = None) -> LLMProvider:
    key = (name or settings.llm_provider).lower()
    if key not in PROVIDERS:
        raise ValueError(f"LLM_PROVIDER desconocido: {key}. Opciones: {', '.join(PROVIDERS)}")
    return PROVIDERS[key]()


__all__ = ["LLMError", "LLMProvider", "PROVIDERS", "build_provider", "clean_code"]
