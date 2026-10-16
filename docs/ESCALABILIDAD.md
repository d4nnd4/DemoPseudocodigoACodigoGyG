# Especificación: de demo a aplicación multiusuario (~30 personas)

Este documento describe qué hay que cambiar para que Pseudo2Code pase de demo local de un solo
usuario a un servicio que usen **al menos 30 personas al mismo tiempo**, y qué máquina hace falta.
Nada de esto está implementado: el demo se mantiene simple a propósito.

> Las cifras de rendimiento son **estimaciones de dimensionamiento** basadas en el tamaño de los
> modelos y el ancho de banda de memoria del hardware. Antes de comprar o contratar, valídalas
> con `scripts/loadtest.py` (sección 6) en la máquina candidata.

## 1. Punto de partida (demo actual)

| Aspecto | Demo | Límite para multiusuario |
|---|---|---|
| Usuarios | Uno, sin login | Todos ven el historial de todos |
| Inferencia | Ollama en CPU, `OLLAMA_NUM_PARALLEL=1` | Una conversión a la vez; las demás esperan |
| Concurrencia | `asyncio.Semaphore(1)` en el proceso | No sirve con varias réplicas del backend |
| Historial | `generated/index.json` | Se reescribe entero en cada cambio; un solo proceso |
| Archivos | Disco local (bind mount) | No compartido entre réplicas |
| Logs | `logs/conversions.jsonl` | Sin consultas, sin métricas agregadas |

## 2. Carga objetivo

Supuestos para 30 usuarios activos a la vez (por ejemplo, un curso o un equipo):

| Variable | Valor supuesto |
|---|---|
| Usuarios activos simultáneos | 30 |
| Frecuencia por usuario | 1 conversión cada ~2 min en uso activo |
| Tasa media | 30 / 120 s ≈ **0,25 conversiones/s** |
| Pico (ráfaga tras «ahora conviertan esto») | **10–15 conversiones simultáneas** |
| Tokens de entrada por conversión | 400 (prompt de sistema) + 100–800 (código) ≈ 1 000 |
| Tokens de salida por conversión | 300–500 típico, 1 536 máximo (`LLM_MAX_TOKENS`) |

Objetivos de servicio (SLO):

- Primer token visible en **< 2 s** (P95) — el streaming hace que la espera se sienta corta.
- Conversión típica (400 tokens) completa en **< 15 s** (P95) → ≥ 25 tokens/s por usuario.
- Throughput agregado en pico: 12 flujos × 25 tok/s ≈ **300 tokens/s**.

## 3. Requisitos de máquina

### Opción recomendada — 1 servidor con GPU de 24 GB

| Componente | Especificación |
|---|---|
| GPU | 1× NVIDIA de **24 GB** (L4, A10/A10G, RTX 4090 o RTX A5000) |
| CPU | 8 vCPU (16 si backend, base de datos y GPU comparten máquina) |
| RAM | 32 GB (64 GB si se quiere margen para un modelo de 14B) |
| Disco | 200 GB NVMe (modelos ~5–15 GB c/u, imágenes Docker, datos y logs) |
| Red | 100 Mbps bastan: el tráfico es texto |
| SO | Linux con driver NVIDIA + NVIDIA Container Toolkit |

Servidor de inferencia: **vLLM** con `Qwen2.5-Coder-7B-Instruct`, preferiblemente cuantizado
a 4 bits (AWQ/GPTQ), con *continuous batching*.

Por qué alcanza:

- Pesos de 7B en 4 bits ≈ 5 GB; en FP16 ≈ 15 GB.
- Caché KV de Qwen2.5-7B (28 capas, 4 cabezas KV de 128): ~56 KB por token.
  32 secuencias × 4 096 tokens ≈ 131 k tokens ≈ **7,3 GB**. Con pesos en 4 bits sobra memoria
  para 32 conversiones simultáneas a contexto completo.
- La generación está limitada por ancho de banda de memoria. Una L4 (≈ 300 GB/s) da del orden de
  40–50 tok/s por flujo con 4 bits (≈ 15–20 con FP16); A10G (≈ 600 GB/s) y RTX 4090 (≈ 1 TB/s)
  permiten FP16 holgado. Con *batching*, el agregado llega a varios cientos de tok/s, por encima
  de los ~300 tok/s del pico.

Parámetros de partida para vLLM:

```bash
--model Qwen/Qwen2.5-Coder-7B-Instruct-AWQ --quantization awq \
--max-model-len 4096 --max-num-seqs 32 --gpu-memory-utilization 0.90
```

### Opción económica — solo CPU (aceptable con poca concurrencia)

| Componente | Especificación |
|---|---|
| CPU | 16 vCPU modernos con AVX2/AVX-512 |
| RAM | 32 GB |
| Disco | 100 GB SSD |
| Modelo | `qwen2.5-coder:1.5b` (o 3b) en Ollama, `OLLAMA_NUM_PARALLEL=4` |

En CPU el throughput agregado ronda unas decenas de tokens/s y se reparte entre las peticiones:
con 10 simultáneas, cada una puede tardar **un minuto o más**. Sirve si las 30 personas no
convierten a la vez (uso escalonado), no para ráfagas de clase.

### Crecimiento (60–150 usuarios)

- 2 GPUs de 24 GB (o 1 de 48 GB) con dos réplicas de vLLM detrás de un balanceador, o un modelo
  de 14B en una GPU de 48 GB si se prioriza calidad.
- El resto de la arquitectura de la sección 4 no cambia: solo se añaden réplicas.

## 4. Arquitectura objetivo

```
                  ┌──────────── Nginx / Ingress (TLS, rate limit, streaming sin buffer) ─────────┐
navegador ──────▶ │  /            frontend estático                                               │
                  │  /api/*  ──▶  backend FastAPI × 2–3 réplicas (stateless)                      │
                  └───────────────────────┬────────────┬─────────────┬───────────────────────────┘
                                          │            │             │
                         ┌────────────────▼──┐  ┌──────▼─────┐  ┌────▼──────────────┐
                         │ PostgreSQL        │  │ Redis      │  │ MinIO / S3        │
                         │ usuarios,         │  │ límites por│  │ archivos          │
                         │ conversiones,     │  │ usuario,   │  │ generados         │
                         │ eventos (logs)    │  │ cupos      │  │ users/<id>/…      │
                         └───────────────────┘  └────────────┘  └───────────────────┘
                                          │
                                          ▼  OpenAI-compatible (LLM_PROVIDER=openai)
                               ┌──────────────────────┐
                               │ vLLM (GPU)           │  métricas → Prometheus → Grafana
                               └──────────────────────┘  logs     → Loki / ELK
```

Todo cabe en **un solo servidor** con Docker Compose para 30 usuarios; Kubernetes solo se
justifica a partir de varias máquinas.

### 4.1 Cambios por componente

| # | Componente | Cambio | Dónde toca el código actual |
|---|---|---|---|
| 1 | Autenticación | OIDC (Keycloak, Entra ID, Google Workspace) o JWT propio. Cada petición lleva `user_id` | Dependencia FastAPI `current_user` en todos los endpoints |
| 2 | Historial | `index.json` → PostgreSQL (tablas abajo). Consultas filtradas por usuario y paginadas | `storage.py`: extraer interfaz `Repository` y crear `PostgresRepository` |
| 3 | Archivos | Disco local → MinIO/S3. Prefijo por usuario: `users/{user}/{language}/{id}_{slug}.ext` | Añadir `{user}` a `TEMPLATE_FIELDS`; escribir con `boto3`/`aioboto3` |
| 4 | Concurrencia | Quitar el `Semaphore` local; el *batching* lo hace vLLM. Cupos en Redis: máx. 2 conversiones activas por usuario y ~20/min | `main.py`: reemplazar `generation_slot` por un limitador Redis |
| 5 | Inferencia | Ollama → vLLM (`LLM_PROVIDER=openai`). El supervisor de Ollama queda para el modo local | Solo `.env` |
| 6 | Logs / trazabilidad | `conversions.jsonl` → tabla `conversion_events` + `user_id`. Logs técnicos en JSON a stdout → Loki | `audit.py`: segundo *sink* a PostgreSQL |
| 7 | Métricas | `/metrics` Prometheus: conversiones por estado, histograma de TTFT y duración, tokens/s, cola | `prometheus-fastapi-instrumentator` + métricas propias en `_convert` |
| 8 | Salud | `/api/health` separa *liveness* (proceso vivo) y *readiness* (modelo listo) para el orquestador | `main.py` |
| 9 | Frontend | Pantalla de login, «mi historial», logs solo para rol admin | `app.js` |

### 4.2 Modelo de datos

```sql
CREATE TABLE users (
  id          uuid PRIMARY KEY,
  email       text UNIQUE NOT NULL,
  role        text NOT NULL DEFAULT 'user',          -- user | admin
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE conversions (
  id          text PRIMARY KEY,                       -- mismo formato que hoy (10 hex)
  user_id     uuid NOT NULL REFERENCES users(id),
  direction   text NOT NULL,                          -- to_code | to_pseudo
  language    text NOT NULL,
  name        text NOT NULL,
  input       text NOT NULL,
  object_key  text NOT NULL,                          -- ruta en S3/MinIO
  model       text NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON conversions (user_id, created_at DESC);

CREATE TABLE conversion_events (                      -- equivalente a conversions.jsonl
  id            bigserial PRIMARY KEY,
  ts            timestamptz NOT NULL DEFAULT now(),
  request_id    text,
  user_id       uuid REFERENCES users(id),
  event         text NOT NULL,                        -- convert | edit | delete
  status        text NOT NULL,                        -- ok | error | cancelled
  conversion_id text,
  direction     text, language text, model text,
  queued_ms int, ttft_ms int, duration_ms int,
  input_chars int, output_chars int, error text
);
CREATE INDEX ON conversion_events (ts DESC);
```

### 4.3 Límites y seguridad

- Tamaño máximo de entrada (hoy 12 000 caracteres) y `LLM_MAX_TOKENS` como tope de costo por petición.
- Rate limit por usuario en Redis y por IP en Nginx (`limit_req`).
- `CORS_ORIGINS` restringido al dominio real; TLS en Nginx.
- El código generado **nunca se ejecuta** en el servidor (si se añade el Profesor de código,
  ver [FUTURO_PROFESOR.md](FUTURO_PROFESOR.md), la ejecución va en un sandbox aislado).
- Copias de seguridad diarias de PostgreSQL y del bucket.

## 5. Despliegue sugerido (un servidor, Docker Compose)

| Servicio | Réplicas | CPU / RAM límite |
|---|---|---|
| nginx + frontend | 1 | 0,5 vCPU / 128 MB |
| backend | 2–3 | 1 vCPU / 512 MB c/u |
| vllm | 1 | toda la GPU, 4 vCPU / 16 GB |
| postgres | 1 | 2 vCPU / 4 GB |
| redis | 1 | 0,5 vCPU / 512 MB |
| minio | 1 | 1 vCPU / 1 GB |
| prometheus + grafana + loki | 1 c/u | 2 vCPU / 4 GB en total |

Suma aproximada: 12–14 vCPU y 28–32 GB de RAM además de la GPU → encaja en la opción
recomendada de la sección 3 (16 vCPU / 32–64 GB / 1× GPU de 24 GB).

## 6. Validación con prueba de carga

`scripts/loadtest.py` lanza N conversiones concurrentes contra `/api/convert` y reporta tiempo al
primer token y duración (P50/P95):

```bash
python scripts/loadtest.py --url http://servidor:8080 --concurrency 12 --requests 36
```

Criterios de aceptación para 30 usuarios:

| Métrica | Objetivo |
|---|---|
| TTFT P95 con 12 concurrentes | < 2 s |
| Duración P95 (≈ 400 tokens) | < 15 s |
| Errores | 0 % |
| Uso de GPU sostenido | < 80 % (margen para picos) |

## 7. Plan por fases

1. **Inferencia**: levantar vLLM y apuntar el demo con `LLM_PROVIDER=openai`. Sin tocar código.
   Correr la prueba de carga. *(La mayor ganancia de capacidad está aquí.)*
2. **Usuarios**: autenticación + PostgreSQL + historial por usuario.
3. **Archivos**: MinIO/S3 con prefijo por usuario.
4. **Operación**: límites en Redis, métricas, logs centralizados, backups.
5. **Réplicas**: 2–3 backends detrás de Nginx; segunda GPU si la prueba de carga lo pide.
