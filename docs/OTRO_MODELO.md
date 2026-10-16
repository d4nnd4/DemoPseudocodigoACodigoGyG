# Usar otro modelo

El backend nunca habla directamente con un modelo: todo pasa por `backend/app/providers/`.
Cada proveedor implementa la misma interfaz (`LLMProvider`), así que cambiar de modelo no toca
los endpoints, el historial, los logs ni el frontend.

```
providers/
  base.py      # interfaz LLMProvider + estado (starting / pulling / loading / ready / error)
  ollama.py    # local: supervisor que descarga, verifica, precalienta, reintenta y vigila
  remote.py    # OpenAI-compatible (OpenAI, Groq, OpenRouter, vLLM, LM Studio…) y Anthropic
  custom.py    # ESPACIO RESERVADO para una API propia (plantilla lista para completar)
  __init__.py  # registro: LLM_PROVIDER -> clase
```

Elige el caso que corresponda a tu modelo. En todos, el cambio se hace en `.env` y se aplica con
`docker compose up -d` (o `--build` si tocaste código).

---

## 1. Otro modelo servido por Ollama (lo más sencillo)

Cualquier modelo de la [librería de Ollama](https://ollama.com/library) o importado con un `Modelfile`.

```bash
# .env
OLLAMA_MODEL=qwen2.5-coder:7b     # o deepseek-coder-v2:16b, codellama:13b, tu-modelo-propio…
OLLAMA_MEM_LIMIT=7g               # súbelo según el tamaño del modelo
```

Al arrancar, el supervisor lo descarga con barra de progreso, verifica que quedó completo
(`/api/tags` + `/api/show`) y lo precalienta. Si la descarga falla, la interfaz lo avisa y se
reintenta sola.

Para un modelo propio en formato GGUF (por ejemplo, el ajustado para AS400 de
[AS400_ENTRENAMIENTO.md](AS400_ENTRENAMIENTO.md)):

```bash
# Modelfile
FROM ./qwen2.5-coder-rpg-q4_k_m.gguf
PARAMETER temperature 0.2
```
```bash
docker compose cp Modelfile ollama:/tmp/Modelfile
docker compose cp qwen2.5-coder-rpg-q4_k_m.gguf ollama:/tmp/
docker compose exec ollama sh -c "cd /tmp && ollama create qwen2.5-coder-rpg -f Modelfile"
# .env -> OLLAMA_MODEL=qwen2.5-coder-rpg
```

## 2. Un servidor con API compatible con OpenAI

Sirve para la nube (OpenAI, Groq, OpenRouter, Together, Mistral, Azure OpenAI) **y** para un
servidor propio más potente: vLLM, TGI, LM Studio o `llama.cpp server`. Es la opción recomendada
para varios usuarios (ver [ESCALABILIDAD.md](ESCALABILIDAD.md)).

```bash
# .env
LLM_PROVIDER=openai
OPENAI_BASE_URL=http://gpu-box:8000/v1
OPENAI_API_KEY=cualquier-cosa          # vLLM la ignora si no configuras --api-key
OPENAI_MODEL=Qwen/Qwen2.5-Coder-7B-Instruct

docker compose up -d --build backend frontend   # sin levantar Ollama
```

Ejemplo de servidor vLLM en una máquina con GPU:

```bash
docker run --gpus all -p 8000:8000 vllm/vllm-openai:<versión> \
  --model Qwen/Qwen2.5-Coder-7B-Instruct --max-model-len 4096 --max-num-seqs 32
```

## 3. Anthropic (Claude)

```bash
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=...
ANTHROPIC_MODEL=...      # ver https://docs.claude.com/en/docs/about-claude/models
```

## 4. Una API propia: el espacio reservado `custom`

Si tu modelo no encaja en nada de lo anterior, completa `backend/app/providers/custom.py`.
Ya está registrado como `custom` y lee estas variables:

```bash
LLM_PROVIDER=custom
CUSTOM_BASE_URL=http://mi-servidor:9000
CUSTOM_API_KEY=
CUSTOM_MODEL=mi-modelo
```

Lo único obligatorio es `stream(system, user)`: un generador asíncrono que emite el texto por
fragmentos. Opcionalmente, `prepare()` (comprobaciones o descargas antes de declararse listo).

```python
class CustomProvider(LLMProvider):
    name = "custom"

    async def prepare(self) -> None:
        # ping, descarga de pesos, warm-up… y al final:
        self.status.set("ready", "Listo")

    async def stream(self, system: str, user: str) -> AsyncIterator[str]:
        async with self.client(self.base_url, settings.llm_timeout) as c:
            async with c.stream("POST", "/generate", json={...}) as resp:
                async for line in resp.aiter_lines():
                    yield json.loads(line)["token"]
```

Reglas:

- Lanza `LLMError` con un mensaje claro ante cualquier fallo: el frontend lo muestra tal cual y
  queda registrado en `logs/conversions.jsonl`.
- Usa `self.client(...)` para crear el cliente HTTP: así los tests pueden inyectar un
  `httpx.MockTransport` sin red (ver `tests/test_providers.py`).
- Si el modelo tarda en estar disponible, sobrescribe `run()` para reintentar, como hace
  `OllamaProvider` (supervisor con backoff + vigilancia).

Para registrar un proveedor con otro nombre, añádelo a `PROVIDERS` en `providers/__init__.py`.
Aparecerá en la pantalla **Configuración** del frontend.

## Ideas de extensión (no implementadas)

- **Un modelo por dirección**: un modelo de código para pseudocódigo → código y uno más pequeño
  para código → pseudocódigo. Bastaría con dos instancias de proveedor en `main.py` y elegir según
  `req.direction`.
- **Selector de modelo en la interfaz**: listar `/api/tags` de Ollama y dejar elegir por
  conversión. Implica cargar/descargar modelos en RAM; en CPU conviene mantener uno solo.
