# Módulo futuro: Profesor de código

> **Estado: diseño, no implementado.** En la interfaz aparece como la pestaña deshabilitada
> «Profesor · próximamente». Este documento deja definido el alcance para construirlo después
> sin rehacer lo que ya existe.

## Objetivo

Ayudar a programar **mejor, más rápido y con menos errores**: no solo traducir, sino explicar por
qué el código es así, detectar errores antes de ejecutarlo y proponer ejercicios para practicar.

## Funcionalidades previstas

| # | Función | Qué hace | Reutiliza |
|---|---|---|---|
| 1 | Revisión de código | Señala errores, malas prácticas y complejidad innecesaria, línea por línea, con la corrección sugerida | Proveedores LLM, editor Monaco (marcadores) |
| 2 | Explicación paso a paso | Recorre el código y explica qué pasa en cada línea con valores de ejemplo (traza de variables) | Conversión código → pseudocódigo |
| 3 | «Explícame este error» | Pega un error de compilación o una excepción y recibe la causa probable y cómo arreglarla | Errores guardados en el pipeline de AS400 |
| 4 | Ejercicios guiados | Enunciado + pruebas ocultas; el alumno escribe, el sistema ejecuta las pruebas y da pistas graduales (no la solución de entrada) | Sección DSA (cada algoritmo genera ejercicios) |
| 5 | Comparar con el óptimo | Tras resolver, muestra la complejidad lograda vs. la óptima y el patrón DSA que aplica | Sección DSA |
| 6 | Progreso | Temas dominados, errores frecuentes, racha de práctica | Logs de trazabilidad |

## Principios pedagógicos

- **Pistas antes que respuestas**: tres niveles (orientación → idea del algoritmo → fragmento),
  la solución completa solo al pedirla explícitamente.
- **Verificación real, no opinión del modelo**: «sin errores» se demuestra ejecutando pruebas y
  herramientas de análisis, no con lo que diga el LLM.
- **Retroalimentación concreta**: cada comentario apunta a una línea y propone un cambio.

## Arquitectura propuesta

```
frontend: pestaña «Profesor»  (editor + panel de comentarios + pruebas)
     │
     ▼
backend/app/tutor/                         ← módulo nuevo, router propio
  router.py      /api/tutor/review | explain | error | exercises | submit
  prompts.py     prompts por función (revisor, explicador, generador de pistas)
  analyzers.py   herramientas estáticas por lenguaje (abajo)
  sandbox.py     cliente del ejecutor aislado
  exercises/     enunciados + pruebas (YAML), ligados a window.DSA
     │                      │
     ▼                      ▼
providers/ (mismos LLM)   sandbox de ejecución (servicio aparte)
```

### Análisis estático (antes de llamar al LLM)

Los hallazgos de estas herramientas se pasan al modelo como contexto: así explica errores reales
en vez de inventarlos.

| Lenguaje | Herramientas |
|---|---|
| Python | `ruff`, `mypy` |
| Go | `go vet`, `staticcheck` |
| TypeScript | `tsc --noEmit`, `eslint` |
| Java | `javac -Xlint` |
| C# / VB.NET | `dotnet build` con analizadores |
| RPGLE | Compilación en IBM i (`CRTBNDRPG`) vía SSH, igual que en AS400_ENTRENAMIENTO.md |

### Sandbox de ejecución

Ejecutar código de usuarios es el mayor riesgo del módulo. Requisitos mínimos:

- Contenedor efímero por ejecución, sin red, sistema de archivos de solo lectura salvo `/tmp`.
- Límites de CPU (1 vCPU), memoria (256 MB), tiempo (5 s) y procesos.
- Aislamiento fuerte: gVisor o Firecracker, o un servicio probado como Judge0 autoalojado.
- Nunca en el mismo contenedor que el backend.

### API (borrador)

| Método | Ruta | Cuerpo → respuesta |
|---|---|---|
| POST | `/api/tutor/review` | `{code, language}` → stream de comentarios `{line, severity, message, fix}` |
| POST | `/api/tutor/explain` | `{code, language, inputs?}` → stream de pasos con traza de variables |
| POST | `/api/tutor/error` | `{code, language, error}` → causa probable + corrección |
| GET | `/api/tutor/exercises?topic=` | lista de ejercicios |
| POST | `/api/tutor/submit` | `{exercise_id, code, language}` → resultado de pruebas + pista siguiente |

Mismo formato de streaming NDJSON que `/api/convert`, y cada llamada se registra en la
trazabilidad con `event: "tutor_*"`.

### Datos (cuando exista multiusuario, ver ESCALABILIDAD.md)

```sql
CREATE TABLE exercises   (id text PRIMARY KEY, topic text, title text, statement text, tests jsonb, difficulty int);
CREATE TABLE submissions (id bigserial PRIMARY KEY, user_id uuid, exercise_id text, language text,
                          code text, passed int, total int, hints_used int, created_at timestamptz DEFAULT now());
```

## Impacto en recursos

- Las revisiones y explicaciones son más largas que una conversión (más tokens de salida):
  estimar ~2× tokens por interacción al dimensionar la GPU.
- El sandbox necesita su propio presupuesto: ~0,5 vCPU y 256 MB por ejecución concurrente.
- Un modelo de 1.5B no alcanza para revisar con calidad; el mínimo razonable es 7B.

## Fases sugeridas

1. **Revisión + «explícame este error»** solo con LLM + análisis estático (sin ejecutar código).
2. **Ejercicios con pruebas** usando el sandbox, empezando por Python y los algoritmos de la
   sección DSA.
3. **Progreso por usuario** (requiere autenticación).
4. Extender a RPGLE con compilación en IBM i.

## Criterios para darlo por listo

- Cada comentario de revisión apunta a una línea existente y la corrección compila.
- Las pruebas de los ejercicios corren en el sandbox en < 5 s.
- Ninguna ejecución puede acceder a la red ni al sistema de archivos del host (prueba de escape
  incluida en el CI).
