import json
import os
import re
import tempfile

os.environ.setdefault("GENERATED_DIR", tempfile.mkdtemp(prefix="gen_"))
os.environ.setdefault("LOGS_DIR", tempfile.mkdtemp(prefix="logs_"))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import main  # noqa: E402
from app.providers import LLMError, LLMProvider, clean_code  # noqa: E402

# Sin `with TestClient(...)` no se ejecuta el lifespan, así que nadie intenta hablar con Ollama.
client = TestClient(main.app)


class FakeProvider(LLMProvider):
    name = "fake"

    def __init__(self, tokens=(), error: str | None = None, ready=True):
        super().__init__("fake-model")
        self.tokens, self.error = tokens, error
        self.prompts = []
        if ready:
            self.status.set("ready", "Listo")

    async def stream(self, system, user):
        self.prompts.append((system, user))
        if self.error:
            raise LLMError(self.error)
        for t in self.tokens:
            yield t


def use(monkeypatch, provider):
    monkeypatch.setattr(main, "provider", provider)


def read_events(resp):
    return [json.loads(line) for line in resp.text.splitlines() if line.strip()]


def generate(**body):
    return client.post("/api/generate", json={"pseudocode": "LEER n\nIMPRIMIR n", **body})


def convert(**body):
    return client.post("/api/convert", json={"source": "LEER n\nIMPRIMIR n", **body})


def test_languages():
    ids = [l["id"] for l in client.get("/api/languages").json()]
    assert ids == ["python", "go", "typescript", "java", "csharp", "vbnet", "asp", "rpgle"]


def test_clean_code_strips_fences():
    assert clean_code("Here you go:\n```python\nprint('hi')\n```\nBye") == "print('hi')\n"
    assert clean_code("```c#\nint x;\n```") == "int x;\n"
    assert clean_code("print(1)") == "print(1)\n"


@pytest.mark.parametrize(
    "lang,suffix",
    [("python", ".py"), ("go", ".go"), ("typescript", ".ts"), ("csharp", ".cs"),
     ("vbnet", ".vb"), ("asp", ".asp"), ("rpgle", ".rpgle"), ("java", "/Main.java")],
)
def test_generate_saves_file(monkeypatch, lang, suffix):
    use(monkeypatch, FakeProvider(["```\n", "code ", "here\n", "```"]))
    events = read_events(generate(language=lang))
    assert [e["type"] for e in events[:-1]] == ["token"] * 4
    item = events[-1]["item"]
    assert events[-1]["type"] == "done"
    assert item["output"] == "code here\n" and item["direction"] == "to_code"
    assert item["model"] == "fake:fake-model"
    assert item["path"].startswith(f"{lang}/") and item["path"].endswith(suffix)
    assert (main.storage.root / item["path"]).read_text() == "code here\n"


def test_history_crud(monkeypatch):
    use(monkeypatch, FakeProvider(["x = 1"]))
    item = read_events(generate(language="java", name="Asignación"))[-1]["item"]
    assert client.get("/api/history").json()[0]["id"] == item["id"]

    assert client.put(f"/api/history/{item['id']}", json={"output": "x = 2\n"}).json()["output"] == "x = 2\n"
    assert client.get(f"/api/history/{item['id']}").json()["output"] == "x = 2\n"
    assert client.get(f"/api/history/{item['id']}/download").text == "x = 2\n"

    folder = (main.storage.root / item["path"]).parent
    assert client.delete(f"/api/history/{item['id']}").status_code == 204
    assert client.get(f"/api/history/{item['id']}").status_code == 404
    assert not folder.exists()  # la carpeta propia de Java se limpia


def test_generate_reports_llm_error(monkeypatch):
    use(monkeypatch, FakeProvider(error="Ollama caído"))
    events = read_events(generate(language="go"))
    assert len(events) == 1 and events[0]["type"] == "error" and events[0]["message"] == "Ollama caído"
    last = client.get("/api/logs?limit=1").json()[0]
    assert last["status"] == "error" and last["error"] == "Ollama caído" and last["language"] == "go"


def test_generate_blocked_until_ready(monkeypatch):
    fake = FakeProvider(["x"], ready=False)
    fake.status.set("pulling", "Descargando modelo…", 42.0)
    use(monkeypatch, fake)
    resp = generate(language="python")
    assert resp.status_code == 503
    assert resp.json()["detail"] == "Descargando modelo…"
    health = client.get("/api/health").json()
    assert health["state"] == "pulling" and health["progress"] == 42.0


def test_rejects_unknown_language(monkeypatch):
    use(monkeypatch, FakeProvider())
    assert generate(language="cobol").status_code == 400


def test_languages_expose_as400_note():
    rpgle = next(l for l in client.get("/api/languages").json() if l["id"] == "rpgle")
    assert "AS400" in rpgle["label"] and "solo" in rpgle["note"]


def test_convert_code_to_pseudocode(monkeypatch):
    fake = FakeProvider(["```\n", "PSEUDOCÓDIGO:\n", "INICIO\n  IMPRIMIR n\nFIN", "\n```"])
    use(monkeypatch, fake)
    code = "def suma_pares(n: int) -> int:\n    return n\n"
    resp = convert(direction="to_pseudo", language="python", source=code)
    events = read_events(resp)
    done = events[-1]
    assert done["type"] == "done" and resp.headers["x-request-id"] == done["request_id"]
    item = done["item"]
    assert item["output"] == "INICIO\n  IMPRIMIR n\nFIN\n"
    assert item["direction"] == "to_pseudo" and item["name"] == "suma_pares"
    assert item["path"].startswith("pseudocode/python/") and item["path"].endswith(".txt")
    assert item["input"] == code
    system, user = fake.prompts[0]
    assert "SPANISH" in system and "Python" in system and code.strip() in user


def test_conversion_is_logged(monkeypatch):
    use(monkeypatch, FakeProvider(["print(1)"]))
    item = read_events(convert(language="python", name="traza"))[-1]["item"]
    rec = client.get("/api/logs", params={"event": "convert", "status": "ok"}).json()[0]
    assert rec["item_id"] == item["id"] and rec["path"] == item["path"]
    assert rec["direction"] == "to_code" and rec["chunks"] == 1 and rec["duration_ms"] >= 0
    client.delete(f"/api/history/{item['id']}")
    assert client.get("/api/logs?limit=1").json()[0]["event"] == "delete"
    assert client.get("/api/logs/download").status_code == 200


def test_legacy_index_is_readable(tmp_path):
    from app.storage import Storage
    (tmp_path / "python").mkdir()
    (tmp_path / "python" / "abc_x.py").write_text("x = 1\n")
    (tmp_path / "index.json").write_text(json.dumps([{
        "id": "abc", "name": "x", "language": "python", "path": "python/abc_x.py",
        "pseudocode": "x <- 1", "model": "m", "created_at": "t", "updated_at": "t"}]))
    item = Storage(tmp_path).get("abc")
    assert item["direction"] == "to_code" and item["input"] == "x <- 1" and item["output"] == "x = 1\n"


def test_path_templates(tmp_path):
    from app.storage import Storage
    st = Storage(tmp_path, code_template="{date}/{language}/{id}", pseudo_template="pseudo/{id}_{slug}",
                 pseudo_extension="pseudo")
    a = st.save(direction="to_code", name="Hola", language="go", input="i", output="o", model="m")
    b = st.save(direction="to_pseudo", name="Hola", language="go", input="i", output="o", model="m")
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}/go/[0-9a-f]{10}\.go", a["path"])
    assert re.fullmatch(r"pseudo/[0-9a-f]{10}_hola\.pseudo", b["path"])


@pytest.mark.parametrize("bad", ["{language}/{slug}", "../{id}", "/abs/{id}", "{user}/{id}"])
def test_invalid_templates_are_rejected(tmp_path, bad):
    from app.storage import Storage
    with pytest.raises(ValueError):
        Storage(tmp_path, code_template=bad)


def test_retry_endpoint_wakes_provider(monkeypatch):
    fake = FakeProvider(ready=False)
    use(monkeypatch, fake)
    assert client.post("/api/model/retry").status_code == 200
    assert fake._retry_pending


def test_config_exposes_paths_without_secrets():
    cfg = client.get("/api/config").json()
    assert cfg["paths"]["code_path_template"] and "custom" in cfg["providers"]
    assert "key" not in json.dumps(cfg).lower()
