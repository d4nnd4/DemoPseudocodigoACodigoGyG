# IBM i / AS400: cómo enseñarle a un modelo

## Situación actual

En la interfaz, AS400 aparece como **«IBM i (AS400) · RPGLE»** con un aviso: de momento solo se
genera y se lee **RPGLE free-format (`**FREE`)**. Quedan fuera CL/CLLE, COBOL/400, DDS (archivos
físicos, lógicos, pantallas) y RPG de formato fijo.

El motivo: los modelos abiertos se entrenan con código público (GitHub, Stack Overflow…) y el
código de IBM i casi no está ahí; vive en servidores privados de bancos, aseguradoras, retail y
manufactura. Un modelo pequeño como `qwen2.5-coder:1.5b` mezcla sintaxis de formato fijo, inventa
*built-in functions* o escribe RPG con estilo de C. Hoy el demo lo mitiga así:

- Prompt que fuerza `**FREE`, `DCL-S`/`DCL-PROC`, `ctl-opt` y `DSPLY` (ver `languages.py`).
- Un ejemplo de estilo dentro del prompt (*few-shot*).
- Pistas para la dirección inversa (qué significa `DSPLY`, `*inlr = *on`…).

Para ir más allá hay tres niveles, de menor a mayor esfuerzo. Conviene hacerlos en orden: cada
uno produce material que el siguiente reutiliza.

---

## Nivel 1 — Mejor prompt + RAG (días, sin GPU)

En vez de entrenar, se le dan al modelo **ejemplos relevantes en cada petición**.

1. Reunir 200–500 fragmentos RPGLE free-format de buena calidad, cada uno con su
   pseudocódigo en español (el formato del conversor) y etiquetas: `dsply`, `sql-embebido`,
   `archivos`, `subprocedimientos`, `data-structures`, `fechas`, `errores-monitor`…
2. Indexarlos con *embeddings* (por ejemplo `nomic-embed-text` en el mismo Ollama) en una base
   vectorial liviana (SQLite + `sqlite-vec`, o Qdrant).
3. En `build_system_prompt` para `rpgle`, recuperar los 3–5 ejemplos más parecidos al
   pseudocódigo de entrada e incluirlos como *few-shot*.

Ganancia típica: menos sintaxis inventada y estilo consistente con la casa. Es la opción más
barata y el corpus sirve tal cual para el nivel 2.

## Nivel 2 — Ajuste fino con LoRA / QLoRA (semanas, 1 GPU de 24 GB)

### 2.1 Qué datos generar

Formato JSONL de conversación, **en ambas direcciones** (así el mismo modelo sirve para
pseudocódigo → RPGLE y RPGLE → pseudocódigo):

```json
{"messages": [
  {"role": "system", "content": "<prompt de sistema de languages.py para rpgle>"},
  {"role": "user", "content": "Translate the following pseudocode into ILE RPG...\n\nPSEUDOCODE:\nLEER n\n..."},
  {"role": "assistant", "content": "**FREE\nctl-opt dftactgrp(*no) actgrp(*caller);\n..."}
]}
```

Usar los **mismos prompts que la app** (`build_system_prompt` / `build_user_prompt`) para que el
modelo vea en producción exactamente lo que vio entrenando.

| Categoría | Pares sugeridos | Notas |
|---|---|---|
| RPGLE básico (variables, bucles, `DSPLY`, subprocedimientos) | 1 500 | Base de todo |
| SQL embebido (`exec sql`, cursores, `SQLRPGLE`) | 800 | Muy usado en sistemas reales |
| Archivos nativos (`DCL-F`, `CHAIN`, `READE`, `SETLL`, `UPDATE`) | 800 | Requiere DDS de los archivos en el contexto |
| Data structures, `LIKEDS`, `QUALIFIED`, arreglos | 500 | |
| Manejo de errores (`MONITOR`/`ON-ERROR`, `%ERROR`, `%STATUS`) | 300 | |
| Fechas, `%DATE`, `%DIFF`, `%SUBDT` | 300 | |
| Formato fijo → free-format (modernización) | 500 | Muy valioso para equipos AS400 |
| CL / CLLE (si se quiere habilitar) | 800 | Lenguaje aparte en `languages.py` |
| DDS (PF/LF/DSPF) | 400 | Ídem |

Entre **3 000 y 8 000 pares** de calidad suelen bastar para un LoRA de dominio sobre un modelo de
código de 7B. Calidad > cantidad.

### 2.2 De dónde sacar los ejemplos

1. **Código propio de la organización**, con autorización explícita. Es la mejor fuente porque
   refleja el estilo real. Antes de usarlo: quitar datos de clientes, credenciales, nombres de
   bibliotecas y servidores internos; revisar que la política de la empresa lo permita.
2. **Generación sintética supervisada**: un modelo grande (vía API) escribe pares
   pseudocódigo ↔ RPGLE a partir de una lista de tareas; **cada par se compila** (paso 2.3) y solo
   se conservan los que pasan.
3. **Código abierto** con licencia que permita el uso (revisar cada repositorio) y la
   documentación de IBM como referencia de sintaxis:
   [ILE RPG Reference](https://www.ibm.com/docs/en/ssw_ibm_i_75/rzasd/rzasdmain.htm).
4. **Modernización**: programas de formato fijo convertidos a `**FREE` (por herramienta o a mano)
   dan pares fijo → free-format muy útiles.

### 2.3 Validación obligatoria: compilar en un IBM i real

Un ejemplo que no compila enseña errores. Pipeline sugerido:

```
par candidato ─▶ subir fuente a QRPGLESRC (SSH/FTP o ODBC) ─▶ CRTBNDRPG / CRTSQLRPGI
              ─▶ ¿compiló? ── no ─▶ descartar (o devolver el error al generador y reintentar)
                           └─ sí ─▶ ejecutar prueba (RPGUnit o CALL con entradas conocidas)
                                    ─▶ ¿salida esperada? ─▶ dataset
```

- Para practicar o para un primer corpus: [PUB400](https://pub400.com/), un IBM i público y
  gratuito.
- Para datos de la empresa: una LPAR o biblioteca de desarrollo propia, nunca producción.
- Guardar también los errores del compilador: sirven para un futuro modo «explícame este error»
  (ver [FUTURO_PROFESOR.md](FUTURO_PROFESOR.md)).
- Separar **10 %** de los pares como conjunto de evaluación que nunca se usa para entrenar.

### 2.4 Entrenamiento

| Elemento | Recomendación |
|---|---|
| Modelo base | `Qwen2.5-Coder-7B-Instruct` (misma familia que el demo; Apache 2.0) |
| Técnica | QLoRA 4 bits (rango 16–32, alpha 32, dropout 0,05) |
| Herramientas | Unsloth, Axolotl o LLaMA-Factory |
| Hardware | 1 GPU de 24 GB (L4, A10G, RTX 4090) |
| Épocas | 2–3, *learning rate* 1e-4 a 2e-4, contexto 4 096 |
| Tiempo | Del orden de horas para ~5 000 pares |

### 2.5 Evaluación

Sobre el 10 % reservado, comparar **modelo base vs. ajustado**:

- **Tasa de compilación** (`CRTBNDRPG` sin errores): la métrica principal.
- **pass@1**: el programa compilado produce la salida esperada.
- Para RPGLE → pseudocódigo: revisión humana con rúbrica corta (¿se entiende?, ¿falta un paso?).
- Regresión: que no empeore en Python/Go/TypeScript (si empeora, mezclar 10–20 % de datos generales).

### 2.6 Llevarlo a la app

```bash
# 1. Fusionar el LoRA con el modelo base y convertir a GGUF (llama.cpp)
python convert_hf_to_gguf.py ./qwen2.5-coder-rpg-merged --outfile qwen2.5-coder-rpg-f16.gguf
./llama-quantize qwen2.5-coder-rpg-f16.gguf qwen2.5-coder-rpg-q4_k_m.gguf Q4_K_M

# 2. Registrarlo en Ollama y apuntar la app (ver OTRO_MODELO.md, caso 1)
ollama create qwen2.5-coder-rpg -f Modelfile
OLLAMA_MODEL=qwen2.5-coder-rpg
```

Alternativa multiusuario: servir el adaptador LoRA en vLLM (`--enable-lora --lora-modules
rpg=./adapter`) y usarlo solo para `rpgle`, dejando el modelo base para los demás lenguajes.

### 2.7 Habilitar más lenguajes de IBM i

Cuando el modelo ajustado compile bien CL o DDS, añadir entradas en `LANGUAGES`
(`backend/app/languages.py`), por ejemplo `clle` (`.clle`) y `dds` (`.pf`, `.dspf`), con sus
`guidelines` y `reverse_hints`, y quitar o actualizar el `note` de `rpgle` que hoy muestra el aviso.

## Nivel 3 — Preentrenamiento continuado (meses)

Solo si se dispone de un corpus muy grande (millones de líneas de código IBM i): entrenar el modelo
base con código crudo antes del ajuste fino. Para la mayoría de los equipos, el nivel 2 con datos
validados por compilación da casi toda la ganancia.

## Riesgos

- **Confidencialidad**: el código de IBM i suele contener lógica de negocio sensible. El
  entrenamiento y la inferencia deben hacerse en infraestructura propia (por eso el demo es local).
- **Licencias**: verificar cada fuente de código abierto.
- **Falsa confianza**: incluso con ajuste fino, el código debe revisarse y probarse antes de
  compilarlo en producción. El aviso de la interfaz debe mantenerse.
