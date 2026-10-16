import asyncio
import json
import logging
import re
import time
import uuid
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from .audit import AuditLog, setup_logging
from .config import settings
from .languages import LANGUAGES, TO_CODE, TO_PSEUDO, build_system_prompt, build_user_prompt
from .providers import PROVIDERS, LLMError, build_provider, clean_code
from .storage import TEMPLATE_FIELDS, Storage

setup_logging(settings.logs_dir, settings.log_level)
log = logging.getLogger("pseudo2code.api")

storage = Storage(
    settings.generated_dir,
    code_template=settings.code_path_template,
    pseudo_template=settings.pseudo_path_template,
    pseudo_extension=settings.pseudo_extension,
)
audit = AuditLog(settings.logs_dir)
provider = build_provider()
# Una conversión a la vez: en CPU, dos en paralelo solo hacen que ambas vayan a la mitad de velocidad.
generation_slot = asyncio.Semaphore(settings.max_concurrent_generations)
queue_size = 0  # peticiones esperando o usando el slot


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Supervisor del modelo en segundo plano: la API responde de inmediato y el
    # frontend muestra el estado / reintentos vía /api/health.
    log.info("Arrancando con proveedor %s (%s)", provider.name, provider.model)
    task = asyncio.create_task(provider.run())
    yield
    task.cancel()


app = FastAPI(title="Pseudo2Code API", version="0.3.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)


class ConvertRequest(BaseModel):
    direction: Literal["to_code", "to_pseudo"] = TO_CODE
    source: str = Field(min_length=3, max_length=12000)
    language: str  # lenguaje destino (to_code) u origen (to_pseudo)
    name: str | None = Field(default=None, max_length=80)


class GenerateRequest(BaseModel):
    """Formato de la v0.2 (solo pseudocódigo -> código). Se mantiene por compatibilidad."""
    pseudocode: str = Field(min_length=3, max_length=12000)
    language: str
    name: str | None = Field(default=None, max_length=80)


class UpdateRequest(BaseModel):
    output: str


_GENERIC_LINES = {"inicio", "begin", "start", "algoritmo", "programa", "proceso", "**free"}
_CODE_NAME_RE = re.compile(
    r"\b(?:def|func|function|class|module|dcl-proc|sub)\s+([A-Za-z_][\w-]*)"      # Python, Go, TS, VB, RPGLE…
    r"|\b(?:static|public|private|protected)\s+[\w<>\[\],]+\s+([A-Za-z_]\w*)\s*\(",  # métodos Java / C#
    re.IGNORECASE,
)
_IGNORED_NAMES = {"main", "program", "page_load", "readline"}
_PSEUDO_LABEL_RE = re.compile(r"^\s*(pseudoc[oó]digo|pseudocode)\s*:?\s*\n", re.IGNORECASE)


def _default_name(source: str, direction: str, language: str = "") -> str:
    if direction == TO_PSEUDO:
        # Primer def / func / class / dcl-proc que no sea main
        for match in _CODE_NAME_RE.finditer(source):
            found = match.group(1) or match.group(2)
            if found.lower() not in _IGNORED_NAMES:
                return found
        return f"programa_{language}" if language else "programa"
    lines = [l.strip() for l in source.splitlines() if l.strip()]
    for line in lines:
        if line.lower().rstrip(":;") not in _GENERIC_LINES and not line.startswith(("import ", "using ", "package ", "#", "//", "<%")):
            return line
    return lines[0] if lines else "programa"


def _clean_output(raw: str, direction: str) -> str:
    text = clean_code(raw)
    if direction == TO_PSEUDO:
        text = _PSEUDO_LABEL_RE.sub("", text, count=1)
    return text


def _ndjson(event: dict) -> str:
    return json.dumps(event, ensure_ascii=False) + "\n"


def _ms(start: float, end: float | None) -> int | None:
    return round((end - start) * 1000) if end else None


@app.get("/api/health")
def health():
    return {**provider.info(), "busy": generation_slot.locked(), "queue": queue_size}


@app.post("/api/model/retry")
async def retry_model():
    """Fuerza un reintento inmediato (o una revisión, si ya estaba listo)."""
    log.info("Reintento manual solicitado desde la interfaz")
    provider.request_retry()
    return provider.info()


@app.get("/api/languages")
def languages():
    return [
        {"id": l.id, "label": l.label, "extension": l.extension, "monaco": l.monaco, "note": l.note}
        for l in LANGUAGES.values()
    ]


@app.get("/api/config")
def config():
    """Configuración efectiva (sin secretos) para la pantalla de Configuración."""
    return {
        "provider": provider.name,
        "model": provider.model,
        "providers": list(PROVIDERS),
        "max_concurrent_generations": settings.max_concurrent_generations,
        "llm_max_tokens": settings.llm_max_tokens,
        "paths": {
            "generated_dir": str(settings.generated_dir),
            "logs_dir": str(settings.logs_dir),
            "generated_host_dir": settings.generated_host_dir,
            "logs_host_dir": settings.logs_host_dir,
            "code_path_template": settings.code_path_template,
            "pseudo_path_template": settings.pseudo_path_template,
            "pseudo_extension": settings.pseudo_extension,
            "template_fields": sorted(TEMPLATE_FIELDS),
        },
    }


async def _convert(req: ConvertRequest, request: Request):
    """Convierte en streaming (NDJSON).

    Eventos: {"type":"queued"} · {"type":"token","content":...}… ·
             {"type":"done","item":{...}} o {"type":"error","message":...}
    """
    lang = LANGUAGES.get(req.language)
    if lang is None:
        raise HTTPException(400, f"Lenguaje no soportado: {req.language}")
    if not provider.ready:
        raise HTTPException(503, provider.status.detail)

    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    system = build_system_prompt(lang, req.direction)
    user = build_user_prompt(req.source, lang, req.direction)
    name = (req.name or _default_name(req.source, req.direction, lang.id))[:80]
    model = f"{provider.name}:{provider.model}"
    client = request.client.host if request.client else None

    async def event_stream():
        global queue_size
        t0 = time.perf_counter()
        t_slot = t_first = None
        raw: list[str] = []
        trace = {"request_id": request_id, "direction": req.direction, "language": lang.id,
                 "model": model, "name": name, "input_chars": len(req.source), "client": client}
        status, error, item = "cancelled", None, None
        queue_size += 1
        try:
            if generation_slot.locked():
                yield _ndjson({"type": "queued", "message": "En cola: hay otra conversión en curso…"})
            async with generation_slot:
                t_slot = time.perf_counter()
                try:
                    async for token in provider.stream(system, user):
                        t_first = t_first or time.perf_counter()
                        raw.append(token)
                        yield _ndjson({"type": "token", "content": token})
                except LLMError as exc:
                    status, error = "error", str(exc)
                    yield _ndjson({"type": "error", "message": error, "request_id": request_id})
                    return

            output = _clean_output("".join(raw), req.direction)
            item = storage.save(direction=req.direction, name=name, language=lang.id,
                                input=req.source, output=output, model=model)
            status = "ok"
            yield _ndjson({"type": "done", "request_id": request_id, "item": {**item, "output": output}})
        finally:
            queue_size -= 1
            t_end = time.perf_counter()
            audit.write(
                "convert", **trace, status=status, error=error,
                queued_ms=_ms(t0, t_slot), ttft_ms=_ms(t_slot, t_first) if t_slot else None,
                duration_ms=_ms(t0, t_end), chunks=len(raw),
                output_chars=len("".join(raw)), item_id=item and item["id"], path=item and item["path"],
            )
            log.info("convert %s %s/%s status=%s %d ms%s", request_id, req.direction, lang.id, status,
                     _ms(t0, t_end), f" error={error}" if error else "")

    return StreamingResponse(event_stream(), media_type="application/x-ndjson",
                             headers={"X-Request-ID": request_id})


@app.post("/api/convert")
async def convert(req: ConvertRequest, request: Request):
    return await _convert(req, request)


@app.post("/api/generate")
async def generate(req: GenerateRequest, request: Request):
    return await _convert(ConvertRequest(direction=TO_CODE, source=req.pseudocode,
                                         language=req.language, name=req.name), request)


@app.get("/api/history")
def history():
    return storage.list()


@app.get("/api/history/{item_id}")
def get_item(item_id: str):
    item = storage.get(item_id)
    if item is None:
        raise HTTPException(404, "No encontrado")
    return item


@app.put("/api/history/{item_id}")
def update_item(item_id: str, req: UpdateRequest):
    item = storage.update_output(item_id, req.output)
    if item is None:
        raise HTTPException(404, "No encontrado")
    audit.write("edit", item_id=item_id, path=item["path"], direction=item["direction"],
                language=item["language"], output_chars=len(req.output), status="ok")
    return item


@app.delete("/api/history/{item_id}", status_code=204)
def delete_item(item_id: str):
    item = storage.delete(item_id)
    if item is None:
        raise HTTPException(404, "No encontrado")
    audit.write("delete", item_id=item_id, path=item["path"], direction=item["direction"],
                language=item["language"], status="ok")


@app.get("/api/history/{item_id}/download")
def download(item_id: str):
    path = storage.file_path(item_id)
    if path is None or not path.exists():
        raise HTTPException(404, "No encontrado")
    return FileResponse(path, filename=path.name, media_type="text/plain")


@app.get("/api/logs")
def logs(limit: int = Query(200, ge=1, le=2000), event: str | None = None, status: str | None = None):
    return audit.tail(limit, event=event, status=status)


@app.get("/api/logs/download")
def download_logs():
    if not audit.path.exists():
        raise HTTPException(404, "Aún no hay registros")
    return FileResponse(audit.path, filename="conversions.jsonl", media_type="application/x-ndjson")
