# Pseudo2Code (demo)

Convierte **pseudocódigo en código** y **código en pseudocódigo** para **Python, Go, TypeScript, Java, C#, Visual Basic .NET, ASP Classic y RPGLE (IBM i / AS400)** usando un LLM open source que corre **100 % local** con [Ollama](https://ollama.com). Sin API keys, sin costo. El resultado se escribe en vivo, token a token, en el editor.

El proveedor de IA es intercambiable: con una variable de entorno se puede pasar a cualquier API compatible con OpenAI o a Anthropic (ver [Usar otro modelo](#usar-otro-modelo)).

```
┌────────────┐   /api/*   ┌──────────────┐  /api/chat  ┌──────────────────────────┐
│  frontend  │ ─────────▶ │   backend    │ ──────────▶ │  ollama                  │
│ Nginx +    │  (stream)  │  FastAPI     │  (stream)   │  qwen2.5-coder (Apache 2)│
│ Monaco     │ ◀───────── │  providers/  │ ◀────────── │  — o OpenAI-compatible / │
└────────────┘            └──────┬───────┘             │    Anthropic             │
                                 │                     └──────────────────────────┘
                                 │ escribe
                                 ▼
                ./generated/<lenguaje>/<id>_<nombre>.<ext>            (código)
                ./generated/pseudocode/<lenguaje>/<id>_<nombre>.txt   (pseudocódigo)
                ./generated/index.json                                (historial)
                ./logs/conversions.jsonl · ./logs/app.log             (trazabilidad)
```

Documentación adicional en [`docs/`](docs/) (también accesible desde la pestaña **Configuración**):

| Guía | Contenido |
|---|---|
| [OTRO_MODELO.md](docs/OTRO_MODELO.md) | Cambiar de modelo: otro de Ollama, vLLM/OpenAI-compatible, Anthropic o una API propia (`custom`) |
| [AS400_ENTRENAMIENTO.md](docs/AS400_ENTRENAMIENTO.md) | Cómo generar datos y ajustar un modelo para IBM i / AS400 |
| [ESCALABILIDAD.md](docs/ESCALABILIDAD.md) | Specs para ~30 usuarios simultáneos: arquitectura, hardware, prueba de carga |
| [FUTURO_PROFESOR.md](docs/FUTURO_PROFESOR.md) | Diseño del módulo futuro «Profesor de código» (no implementado) |

## Requisitos

- Docker + Docker Compose v2
- ~3 GB libres de disco (imagen de Ollama + modelo de ~1 GB)
- 8 GB de RAM recomendados

## Arranque

```bash
cp .env.example .env        # opcional, para cambiar modelo o puerto
docker compose up --build
```

Abre **http://localhost:8080**.

La primera vez el backend descarga el modelo (queda cacheado en el volumen `ollama-models`), verifica que quedó completo y lo carga en memoria. Mientras tanto, una franja bajo la barra superior muestra el progreso y el botón de conversión queda bloqueado. Las siguientes veces arranca en segundos.

### Disponibilidad del modelo (descargas fallidas)

A veces la descarga de qwen se corta o queda incompleta. El backend tiene un **supervisor** que no declara el modelo listo hasta comprobarlo:

1. Espera a Ollama → ¿está el modelo? → si no, lo descarga (`/api/pull`).
2. **Verifica**: la descarga debe terminar con `success` y el modelo debe aparecer en `/api/tags` y responder a `/api/show`. Si la descarga se queda sin avanzar `OLLAMA_PULL_STALL_SECONDS` (120 s), se corta.
3. Lo precalienta y solo entonces lo marca como listo.
4. Si algo falla, **avisa al usuario** (franja amarilla con el motivo, el número de intento y la cuenta regresiva) y **reintenta solo** con backoff exponencial de 5 s a 60 s. Ollama reanuda las capas ya descargadas. El botón **Reintentar ahora** salta la espera.
5. Ya listo, cada `OLLAMA_WATCHDOG_SECONDS` (60 s) comprueba que el modelo siga ahí; si alguien borra el volumen o Ollama se cae, vuelve al paso 1 y la interfaz vuelve a avisar.

Todo queda en `logs/app.log`.

### Con GPU NVIDIA (opcional)

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build
```

## Uso

1. Elige la dirección: **Pseudocódigo → Código** o **Código → Pseudocódigo**.
2. Escribe la entrada (o **Cargar ejemplo**), elige el lenguaje (destino u origen) y, si quieres, un nombre.
3. **Generar** (o `Ctrl/Cmd + Enter`). El resultado aparece token a token; abajo se ven los fragmentos y el tiempo.
4. Se guarda automáticamente. Puedes editarlo y **Guardar** (`Ctrl/Cmd + S`), copiarlo, descargarlo o **⇄ Invertir**: el resultado pasa a ser la entrada en la dirección contraria (ida y vuelta).
5. El historial de la izquierda permite reabrir o borrar conversiones anteriores.

Otras pestañas:

- **Logs**: trazabilidad de cada conversión (estado, modelo, cola, tiempo al primer token, duración, tamaños, archivo y `request_id`), con filtros y descarga del `.jsonl`.
- **DSA y recursos**: los algoritmos más útiles (búsqueda binaria, dos punteros, ventana deslizante, BFS/DFS, Dijkstra, orden topológico, union-find, programación dinámica, backtracking, trie…) con complejidad, cuándo usarlos y su pseudocódigo listo para **Convertir** a cualquier lenguaje; más la documentación oficial de cada lenguaje.
- **Configuración**: modelo activo, rutas de salvado efectivas e instrucciones para usar otro modelo.
- **Profesor** (deshabilitada): módulo futuro, ver [FUTURO_PROFESOR.md](docs/FUTURO_PROFESOR.md).

Tema claro u oscuro con el botón ◐ (por defecto, el del sistema). La paleta sale del logo: azul marino, teal y plata.

## Lenguajes

| Lenguaje | Archivo generado | Notas del prompt |
|---|---|---|
| Python 3.12 | `.py` | type hints, `if __name__ == "__main__"` |
| Go 1.22 | `.go` | `package main`, solo stdlib |
| TypeScript 5 | `.ts` | Node.js, sin `any` |
| Java 21 | `<id>_<nombre>/Main.java` | carpeta propia para que compile tal cual (`javac Main.java`) |
| C# 12 / .NET 8 | `.cs` | clase `Program` con `Main` |
| Visual Basic .NET | `.vb` | `Option Strict On`, `Module Program` |
| ASP Classic | `.asp` | VBScript, `Request.Form`, `Server.HTMLEncode` |
| IBM i (AS400) · RPGLE | `.rpgle` | free-format `**FREE` |

En la dirección inversa, el pseudocódigo se guarda como `pseudocode/<lenguaje>/<id>_<nombre>.txt`, en español y con las mismas palabras clave que acepta la entrada (`INICIO`, `LEER`, `SI … ENTONCES`, `PARA … HASTA`, `FUNCION`, `<-`…).

Para añadir otro, agrega una entrada en `LANGUAGES` (`backend/app/languages.py`). El frontend lo toma automáticamente.

> **AS400:** de momento solo está disponible **RPGLE free-format**; la interfaz lo indica al elegirlo. CL, COBOL/400 y DDS no están soportados porque los modelos abiertos casi no tienen datos de entrenamiento de IBM i. Cómo cambiar eso: [AS400_ENTRENAMIENTO.md](docs/AS400_ENTRENAMIENTO.md).

## Rutas de salvado y logs

Todo se configura en `.env`:

| Variable | Default | Efecto |
|---|---|---|
| `GENERATED_HOST_DIR` | `./generated` | Carpeta del host donde quedan los archivos (relativa o absoluta) |
| `LOGS_HOST_DIR` | `./logs` | Carpeta del host para `app.log` y `conversions.jsonl` |
| `CODE_PATH_TEMPLATE` | `{language}/{id}_{slug}` | Ruta de cada archivo de código (sin extensión) |
| `PSEUDO_PATH_TEMPLATE` | `pseudocode/{language}/{id}_{slug}` | Ruta de cada pseudocódigo |
| `PSEUDO_EXTENSION` | `txt` | Extensión del pseudocódigo |

Variables de las plantillas: `{language} {direction} {id} {slug} {date} {year} {month}`. `{id}` es obligatorio y no se permiten rutas absolutas ni `..` (el backend no arranca si la plantilla es inválida). Por ejemplo, `CODE_PATH_TEMPLATE={year}/{month}/{language}/{id}_{slug}` agrupa por fecha. La pestaña **Configuración** muestra los valores efectivos y una vista previa.

`logs/conversions.jsonl` tiene una línea por evento (`convert`, `edit`, `delete`):

```json
{"ts": "2026-10-16T16:21:08.063+00:00", "event": "convert", "request_id": "7142ca3e1c95",
 "direction": "to_code", "language": "python", "model": "ollama:qwen2.5-coder:1.5b", "name": "LEER n",
 "input_chars": 253, "client": "172.18.0.4", "status": "ok", "error": null, "queued_ms": 0,
 "ttft_ms": 86, "duration_ms": 2385, "chunks": 75, "output_chars": 299,
 "item_id": "cfbb48b9f0", "path": "python/cfbb48b9f0_leer_n.py"}
```

`status` es `ok`, `error` (con el mensaje) o `cancelled` (el usuario cerró la página a mitad). El `request_id` también va en la cabecera `X-Request-ID` de la respuesta y en `app.log`.

## Modelo y consumo de recursos

Por defecto `qwen2.5-coder:1.5b` (~1.2 GB de RAM, rápido en CPU). Todo se ajusta en `.env`:

| Variable | Default | Efecto |
|---|---|---|
| `OLLAMA_MODEL` | `qwen2.5-coder:1.5b` | `0.5b` para equipos modestos, `7b` para mejor calidad |
| `OLLAMA_NUM_CTX` | `4096` | Ventana de contexto. `2048` reduce RAM si el pseudocódigo es corto |
| `OLLAMA_KEEP_ALIVE` | `15m` | Tras ese tiempo sin uso el modelo sale de la RAM (vuelve a cargarse solo) |
| `OLLAMA_MEM_LIMIT` | `3g` | Tope de memoria del contenedor. Súbelo a `7g` si usas el 7b |
| `LLM_MAX_TOKENS` | `1536` | Tope de salida: corta respuestas que se alargan sin fin |
| `OLLAMA_RETRY_MIN_SECONDS` / `_MAX_SECONDS` | `5` / `60` | Backoff de reintentos mientras el modelo no está disponible |
| `OLLAMA_PULL_STALL_SECONDS` | `120` | Descarga sin avanzar este tiempo = se corta y se reintenta |
| `OLLAMA_WATCHDOG_SECONDS` | `60` | Cada cuánto se comprueba, ya listo, que el modelo siga existiendo |

Además, ya vienen activadas estas optimizaciones:

- **Ollama:** una sola petición y un solo modelo en memoria (`OLLAMA_NUM_PARALLEL=1`, `OLLAMA_MAX_LOADED_MODELS=1`), *flash attention* y caché de contexto cuantizada a 8 bits (`OLLAMA_KV_CACHE_TYPE=q8_0`).
- **Backend:** una generación a la vez. Si llega otra, espera en cola en vez de repartir la CPU entre las dos. Límite de 0.5 CPU / 256 MB.
- **Frontend:** Nginx Alpine con 64 MB. Consulta el estado cada 2 s solo mientras el modelo se prepara y cada 30 s cuando ya está listo. El streaming añade cada fragmento al final del editor en vez de reescribirlo entero.
- Se eliminó el contenedor `ollama-init` y los *healthchecks* periódicos.

## Usar otro modelo

El backend habla con la IA a través de `backend/app/providers/`. Cada proveedor implementa la misma interfaz (`LLMProvider`: `stream()` y opcionalmente `prepare()` / `run()`), así que cambiar de modelo no toca el resto de la app:

```
providers/
  base.py      # interfaz LLMProvider + estado (starting/pulling/loading/ready/error, intento, reintento)
  ollama.py    # local: supervisor que descarga, verifica, precalienta, reintenta y vigila
  remote.py    # OpenAI-compatible (OpenAI, Groq, OpenRouter, vLLM, LM Studio…) y Anthropic
  custom.py    # espacio reservado para una API propia (LLM_PROVIDER=custom)
  __init__.py  # registro: LLM_PROVIDER -> clase
```

Guía paso a paso de cada caso: [docs/OTRO_MODELO.md](docs/OTRO_MODELO.md).

Por ejemplo, para usar un modelo en la nube compatible con OpenAI:

```bash
# .env
LLM_PROVIDER=openai
OPENAI_BASE_URL=https://api.groq.com/openai/v1
OPENAI_API_KEY=...
OPENAI_MODEL=...

docker compose up --build backend frontend   # sin levantar Ollama
```

Para Anthropic usa `LLM_PROVIDER=anthropic`, `ANTHROPIC_API_KEY` y `ANTHROPIC_MODEL`. La opción `openai` también sirve para un servidor propio más potente (vLLM, TGI o LM Studio en una máquina con GPU): solo cambia `OPENAI_BASE_URL`.

Para un proveedor nuevo: completa la plantilla `providers/custom.py` (ya registrada como `custom`) o crea otra clase que herede de `LLMProvider` y regístrala en `PROVIDERS`.

Para varios usuarios a la vez, el camino es un servidor vLLM con GPU detrás de `LLM_PROVIDER=openai`: ver [docs/ESCALABILIDAD.md](docs/ESCALABILIDAD.md) (specs para ~30 usuarios y `scripts/loadtest.py` para validarlas).

> Estas integraciones son demostrativas: los tests las verifican con respuestas HTTP simuladas, no contra las APIs reales.

> **Nota sobre RPGLE:** es un lenguaje con poca presencia en los datos de entrenamiento, así que los modelos pequeños cometen más errores. El prompt fuerza **free-format (`**FREE`)** e incluye un ejemplo de estilo; con `qwen2.5-coder:7b` o superior los resultados mejoran bastante. Revisa siempre el código antes de compilarlo en el IBM i.

## API

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/health` | Proveedor, modelo, estado (`starting` / `pulling` + `progress` / `loading` / `ready` / `error`), `attempt`, `last_error`, `retry_in`, cola |
| POST | `/api/model/retry` | Reintenta preparar el modelo ya (o lo revisa si estaba listo) |
| GET | `/api/languages` | Lenguajes soportados (con `note`, p. ej. el aviso de AS400) |
| GET | `/api/config` | Configuración efectiva sin secretos: proveedor, rutas, plantillas |
| POST | `/api/convert` | `{direction: "to_code"\|"to_pseudo", source, language, name?}` → stream NDJSON (`queued`, `token`…, `done` con el ítem guardado). `503` si el modelo no está listo |
| POST | `/api/generate` | Formato anterior `{pseudocode, language, name?}` (equivale a `to_code`) |
| GET | `/api/history` | Historial |
| GET / PUT / DELETE | `/api/history/{id}` | Ver, guardar edición (`{output}`) o borrar |
| GET | `/api/history/{id}/download` | Descargar el archivo |
| GET | `/api/logs?limit=&event=&status=` | Últimos eventos de trazabilidad (más recientes primero) |
| GET | `/api/logs/download` | Descargar `conversions.jsonl` |

Documentación interactiva de FastAPI (sin pasar por Nginx): `docker compose exec backend curl localhost:8000/docs` o exponiendo el puerto 8000.

## Estructura

```
backend/
  app/
    main.py        # endpoints FastAPI, supervisor del modelo en segundo plano, cola, trazas
    providers/     # Ollama (supervisor), OpenAI-compatible, Anthropic, custom
    languages.py   # catálogo de lenguajes y prompts por dirección
    storage.py     # archivos en disco con rutas por plantilla + index.json
    audit.py       # app.log + conversions.jsonl
    config.py      # variables de entorno
  tests/           # pytest (proveedores y supervisor con HTTP simulado)
frontend/
  index.html, app.js, styles.css
  monaco-langs.js  # resaltado de RPGLE y del pseudocódigo + temas del logo
  resources.js     # contenido de «DSA y recursos»
  assets/          # logo y favicon
  Dockerfile       # empaqueta Monaco desde npm (no depende de CDN) y sirve docs/
docs/              # guías: otro modelo, AS400, escalabilidad, profesor (futuro)
scripts/
  loadtest.py      # prueba de carga para dimensionar el servidor
generated/         # aquí queda lo generado (GENERATED_HOST_DIR)
logs/              # trazabilidad (LOGS_HOST_DIR)
```

## Tests

```bash
cd backend
pip install -r requirements.txt pytest
pytest            # pytest.ini ya configura el pythonpath
```
