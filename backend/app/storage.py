"""
Este es el módulo de persistencia en disco: un archivo por conversión añadiendo `index.json` con el historial.

La ruta de cada archivo sale de una plantilla configurable (CODE_PATH_TEMPLATE /
PSEUDO_PATH_TEMPLATE). Por defecto:
    código       -> <language>/<id>_<slug>.<ext>           (Java: <language>/<id>_<slug>/Main.java)
    pseudocódigo -> pseudocode/<language>/<id>_<slug>.txt
"""

import json
import re
import string
import threading
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .languages import LANGUAGES, TO_CODE, TO_PSEUDO

TEMPLATE_FIELDS = {"language", "direction", "id", "slug", "date", "year", "month"}


def slugify(text: str, max_len: int = 40) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
    return text[:max_len].rstrip("_") or "programa"


def validate_template(template: str) -> str:
    """Falla al arrancar si la plantilla usa variables desconocidas o intenta salir de la raíz."""
    fields = {f for _, f, _, _ in string.Formatter().parse(template) if f}
    unknown = fields - TEMPLATE_FIELDS
    if unknown:
        raise ValueError(f"Variables desconocidas en la plantilla '{template}': {sorted(unknown)}. "
                         f"Permitidas: {sorted(TEMPLATE_FIELDS)}")
    if "{id}" not in template:
        raise ValueError(f"La plantilla '{template}' debe incluir {{id}} para no sobrescribir archivos")
    if template.startswith("/") or ".." in Path(template).parts:
        raise ValueError(f"La plantilla '{template}' debe ser una ruta relativa sin '..'")
    return template


def _normalize(item: dict) -> dict:
    """Compatibilidad con índices de la versión anterior (solo pseudocódigo -> código)."""
    if "direction" not in item:
        item = {**item, "direction": TO_CODE, "input": item.get("pseudocode", "")}
        item.pop("pseudocode", None)
    return item


class Storage:
    def __init__(self, root: Path, *, code_template: str = "{language}/{id}_{slug}",
                 pseudo_template: str = "pseudocode/{language}/{id}_{slug}", pseudo_extension: str = "txt"):
        self.root = root
        self.index_path = root / "index.json"
        self.templates = {TO_CODE: validate_template(code_template), TO_PSEUDO: validate_template(pseudo_template)}
        self.pseudo_extension = pseudo_extension.lstrip(".")
        self._lock = threading.Lock()
        self.root.mkdir(parents=True, exist_ok=True)
        if not self.index_path.exists():
            self._write_index([])

    def _read_index(self) -> list[dict]:
        try:
            return [_normalize(i) for i in json.loads(self.index_path.read_text(encoding="utf-8"))]
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _write_index(self, items: list[dict]) -> None:
        tmp = self.index_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.index_path)

    def _find(self, items: list[dict], item_id: str) -> dict | None:
        return next((i for i in items if i["id"] == item_id), None)

    def _safe_path(self, rel_path: str) -> Path:
        path = (self.root / rel_path).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise ValueError("Ruta fuera del directorio de salida")
        return path

    def build_rel_path(self, *, direction: str, language: str, item_id: str, name: str,
                       now: datetime | None = None) -> Path:
        lang = LANGUAGES[language]
        now = now or datetime.now(timezone.utc)
        base = Path(self.templates[direction].format(
            language=language, direction=direction, id=item_id, slug=slugify(name),
            date=now.strftime("%Y-%m-%d"), year=now.strftime("%Y"), month=now.strftime("%m"),
        ))
        if direction == TO_PSEUDO:
            return base.with_name(f"{base.name}.{self.pseudo_extension}")
        if lang.fixed_filename:
            return base / lang.fixed_filename  # carpeta propia, p. ej. Java -> .../Main.java
        return base.with_name(f"{base.name}.{lang.extension}")

    def save(self, *, direction: str, name: str, language: str, input: str, output: str, model: str) -> dict:
        item_id = uuid.uuid4().hex[:10]
        rel_path = self.build_rel_path(direction=direction, language=language, item_id=item_id, name=name)
        abs_path = self._safe_path(rel_path.as_posix())
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_text(output, encoding="utf-8")

        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        item = {
            "id": item_id,
            "name": name,
            "direction": direction,
            "language": language,
            "path": rel_path.as_posix(),
            "input": input,
            "model": model,
            "created_at": now,
            "updated_at": now,
        }
        with self._lock:
            items = self._read_index()
            items.insert(0, item)
            self._write_index(items)
        return item

    def list(self) -> list[dict]:
        return self._read_index()

    def get(self, item_id: str) -> dict | None:
        item = self._find(self._read_index(), item_id)
        if item is None:
            return None
        path = self._safe_path(item["path"])
        return {**item, "output": path.read_text(encoding="utf-8") if path.exists() else ""}

    def file_path(self, item_id: str) -> Path | None:
        item = self._find(self._read_index(), item_id)
        return self._safe_path(item["path"]) if item else None

    def update_output(self, item_id: str, output: str) -> dict | None:
        with self._lock:
            items = self._read_index()
            item = self._find(items, item_id)
            if item is None:
                return None
            self._safe_path(item["path"]).write_text(output, encoding="utf-8")
            item["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            self._write_index(items)
        return {**item, "output": output}

    def delete(self, item_id: str) -> dict | None:
        with self._lock:
            items = self._read_index()
            item = self._find(items, item_id)
            if item is None:
                return None
            path = self._safe_path(item["path"])
            path.unlink(missing_ok=True)
            # Limpia carpetas que quedaron vacías (p. ej. la carpeta propia de Java), sin tocar la raíz
            parent = path.parent
            while parent != self.root.resolve() and parent.exists() and not any(parent.iterdir()):
                parent.rmdir()
                parent = parent.parent
            self._write_index([i for i in items if i["id"] != item_id])
        return item
