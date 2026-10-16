"""
Con este módulo se debe dejar configuraciones parametrizadas. De lo contrario, todo quedaría fijo y entorpecería 
el proceso de monitoreo de la implementación con IA.

Proveedor: OLlama (local) | OpenAI con API | Anthropic | Otro
"""

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings

_DEFAULT_TEMPLATES = {
    "code_path_template": "{language}/{id}_{slug}",
    "pseudo_path_template": "pseudocode/{language}/{id}_{slug}",
}


class Settings(BaseSettings):
    # ollama (local, por defecto)
    llm_provider: str = "ollama"
    llm_temperature: float = 0.2
    llm_max_tokens: int = 1536          
    llm_timeout: float = 600.0
    max_concurrent_generations: int = 1  

    # Ollama
    ollama_url: str = "http://ollama:11434"
    ollama_model: str = "qwen2.5-coder:1.5b"
    ollama_num_ctx: int = 4096          # menos RAM
    ollama_keep_alive: str = "15m"      
    ollama_auto_pull: bool = True       # descarga el modelo si falta
    
    ollama_retry_min_seconds: float = 5.0
    ollama_retry_max_seconds: float = 60.0
    
    ollama_pull_stall_seconds: float = 120.0
    
    ollama_watchdog_seconds: float = 60.0

    # OpenAI-compatible (OpenAI, Groq, OpenRouter, Together, vLLM, LM Studio…)
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = ""
    openai_model: str = ""

    # Anthropic
    anthropic_base_url: str = "https://api.anthropic.com"
    anthropic_api_key: str = ""
    anthropic_model: str = ""

    # Proveedor propio (plantilla en providers/custom.py)
    custom_base_url: str = ""
    custom_api_key: str = ""
    custom_model: str = ""

    # --- Rutas de salida -------------------------------------------------------
    generated_dir: Path = Path("/data/generated")
    logs_dir: Path = Path("/data/logs")
    # Plantillas de la ruta relativa de cada archivo (sin extensión).
    # Variables: {language} {direction} {id} {slug} {date} {year} {month}
    code_path_template: str = _DEFAULT_TEMPLATES["code_path_template"]
    pseudo_path_template: str = _DEFAULT_TEMPLATES["pseudo_path_template"]
    pseudo_extension: str = "txt"
    # Solo informativos (los muestra la pantalla de Configuración): rutas reales en el host
    generated_host_dir: str = ""
    logs_host_dir: str = ""

    # --- App Level ---------------------------------------------------------------
    log_level: str = "INFO"
    cors_origins: str = "*"

    @field_validator("code_path_template", "pseudo_path_template", mode="before")
    @classmethod
    def _empty_means_default(cls, value, info):
        return value.strip() if value and value.strip() else _DEFAULT_TEMPLATES[info.field_name]


settings = Settings()
