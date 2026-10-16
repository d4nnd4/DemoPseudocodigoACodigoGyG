"""Proveedores probados contra transportes HTTP simulados (sin red)."""

import asyncio
import json

import httpx
import pytest

from app.config import settings
from app.providers import PROVIDERS, build_provider
from app.providers.ollama import OllamaProvider
from app.providers.remote import AnthropicProvider, OpenAICompatibleProvider


def collect(provider):
    async def run():
        return [t async for t in provider.stream("sys", "user")]
    return asyncio.run(run())


def ndjson(*events):
    return "".join(json.dumps(e) + "\n" for e in events)


def sse(*events):
    return "".join(f"data: {json.dumps(e) if not isinstance(e, str) else e}\n\n" for e in events)


def test_ollama_prepare_pulls_and_warms_up():
    calls, progress_seen, pulled = [], [], []

    def handler(req: httpx.Request):
        calls.append(req.url.path)
        if req.url.path == "/api/version":
            return httpx.Response(200, json={"version": "x"})
        if req.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": settings.ollama_model}] if pulled else []})
        if req.url.path == "/api/show":
            return httpx.Response(200, json={})
        if req.url.path == "/api/pull":
            pulled.append(True)
            return httpx.Response(200, text=ndjson(
                {"status": "pulling", "digest": "a", "total": 100, "completed": 50},
                {"status": "pulling", "digest": "a", "total": 100, "completed": 100},
                {"status": "success"},
            ))
        if req.url.path == "/api/generate":
            body = json.loads(req.content)
            assert "prompt" not in body and body["keep_alive"] == settings.ollama_keep_alive
            progress_seen.append(provider.status.state)
            return httpx.Response(200, json={"done": True})
        return httpx.Response(404)

    provider = OllamaProvider(url="http://ollama", transport=httpx.MockTransport(handler))
    asyncio.run(provider.prepare())
    assert calls == ["/api/version", "/api/tags", "/api/pull", "/api/tags", "/api/show", "/api/generate"]
    assert progress_seen == ["loading"]
    assert provider.ready


def test_ollama_skips_pull_when_model_present():
    def handler(req):
        if req.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": settings.ollama_model}]})
        assert req.url.path != "/api/pull"
        return httpx.Response(200, json={})

    provider = OllamaProvider(url="http://ollama", transport=httpx.MockTransport(handler))
    asyncio.run(provider.prepare())
    assert provider.ready


def test_ollama_stream_sends_resource_options():
    def handler(req):
        body = json.loads(req.content)
        assert body["options"]["num_ctx"] == settings.ollama_num_ctx
        assert body["options"]["num_predict"] == settings.llm_max_tokens
        return httpx.Response(200, text=ndjson(
            {"message": {"content": "print("}}, {"message": {"content": "1)"}}, {"done": True}))

    provider = OllamaProvider(url="http://ollama", transport=httpx.MockTransport(handler))
    assert collect(provider) == ["print(", "1)"]


def test_openai_compatible_stream(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    monkeypatch.setattr(settings, "openai_model", "some-model")

    def handler(req):
        assert req.url.path.endswith("/chat/completions")
        assert req.headers["authorization"] == "Bearer sk-test"
        return httpx.Response(200, text=sse(
            {"choices": [{"delta": {"role": "assistant"}}]},
            {"choices": [{"delta": {"content": "fmt."}}]},
            {"choices": [{"delta": {"content": "Println()"}}]},
            "[DONE]",
        ))

    provider = OpenAICompatibleProvider(transport=httpx.MockTransport(handler))
    asyncio.run(provider.prepare())
    assert provider.ready
    assert collect(provider) == ["fmt.", "Println()"]


def test_anthropic_stream(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "ak-test")
    monkeypatch.setattr(settings, "anthropic_model", "some-claude")

    def handler(req):
        body = json.loads(req.content)
        assert req.headers["x-api-key"] == "ak-test" and body["system"] == "sys"
        return httpx.Response(200, text=sse(
            {"type": "message_start"},
            {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Dim x"}},
            {"type": "content_block_delta", "delta": {"type": "text_delta", "text": " As Integer"}},
            {"type": "message_stop"},
        ))

    provider = AnthropicProvider(transport=httpx.MockTransport(handler))
    asyncio.run(provider.prepare())
    assert collect(provider) == ["Dim x", " As Integer"]


def test_remote_provider_without_key_is_not_ready(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "")
    provider = OpenAICompatibleProvider()
    asyncio.run(provider.prepare())
    assert provider.status.state == "error" and "API key" in provider.status.detail


def test_registry():
    assert set(PROVIDERS) == {"ollama", "openai", "anthropic", "custom"}
    with pytest.raises(ValueError):
        build_provider("nope")


@pytest.fixture
def fast_retries(monkeypatch):
    monkeypatch.setattr(settings, "ollama_retry_min_seconds", 0.01)
    monkeypatch.setattr(settings, "ollama_retry_max_seconds", 0.02)
    monkeypatch.setattr(settings, "ollama_watchdog_seconds", 0.01)


class FlakyOllama:
    """Ollama simulado: la descarga se corta `fail_pulls` veces antes de completarse."""

    def __init__(self, fail_pulls=0, server_down_checks=0):
        self.fail_pulls, self.server_down_checks = fail_pulls, server_down_checks
        self.has_model, self.calls = False, []

    def __call__(self, req: httpx.Request):
        path = req.url.path
        self.calls.append(path)
        if path == "/api/version":
            if self.server_down_checks:
                self.server_down_checks -= 1
                raise httpx.ConnectError("connection refused")
            return httpx.Response(200, json={"version": "x"})
        if path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": settings.ollama_model}] if self.has_model else []})
        if path == "/api/pull":
            if self.fail_pulls:
                self.fail_pulls -= 1
                # Stream que termina a medias: nunca llega {"status": "success"}
                return httpx.Response(200, text=ndjson({"status": "pulling", "digest": "a", "total": 10, "completed": 3}))
            self.has_model = True
            return httpx.Response(200, text=ndjson({"status": "success"}))
        if path == "/api/show":
            return httpx.Response(200 if self.has_model else 404, json={})
        return httpx.Response(200, json={"done": True})


def test_interrupted_pull_is_reported_and_retried(fast_retries):
    fake = FlakyOllama(fail_pulls=2, server_down_checks=1)
    provider = OllamaProvider(url="http://ollama", transport=httpx.MockTransport(fake))
    states = []
    original_sleep = provider._sleep_or_wake

    async def spy(seconds):
        states.append((provider.status.state, provider.status.attempt, provider.status.last_error))
        assert provider.status.as_dict()["retry_in"] is not None
        return await original_sleep(seconds)

    provider._sleep_or_wake = spy
    asyncio.run(provider.ensure_ready())
    assert provider.ready and provider.status.attempt == 0 and provider.status.last_error is None
    assert states[0][0] == "starting" and "no responde" in states[0][2]
    assert [s[0] for s in states[1:]] == ["error", "error"]
    assert all("interrumpi" in s[2] for s in states[1:])
    assert [s[1] for s in states] == [1, 2, 3]
    assert fake.calls.count("/api/pull") == 3


def test_pull_error_event_is_not_ready():
    def handler(req):
        if req.url.path == "/api/tags":
            return httpx.Response(200, json={"models": []})
        if req.url.path == "/api/pull":
            return httpx.Response(200, text=ndjson({"error": "no space left on device"}))
        return httpx.Response(200, json={})

    provider = OllamaProvider(url="http://ollama", transport=httpx.MockTransport(handler))
    with pytest.raises(Exception, match="no space left"):
        asyncio.run(provider.prepare())
    assert not provider.ready


def test_incomplete_model_fails_verification():
    def handler(req):
        if req.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": settings.ollama_model}]})
        if req.url.path == "/api/show":
            return httpx.Response(500, json={"error": "blob missing"})
        return httpx.Response(200, json={})

    provider = OllamaProvider(url="http://ollama", transport=httpx.MockTransport(handler))
    with pytest.raises(Exception, match="incompleto"):
        asyncio.run(provider.prepare())


def test_watchdog_detects_missing_model(fast_retries):
    fake = FlakyOllama()
    fake.has_model = True
    provider = OllamaProvider(url="http://ollama", transport=httpx.MockTransport(fake))
    provider.status.set("ready", "Listo")

    async def scenario():
        watcher = asyncio.create_task(provider._watch())
        await asyncio.sleep(0.05)
        assert not watcher.done()      # el modelo sigue ahí: sigue vigilando
        fake.has_model = False         # alguien borró el volumen
        await asyncio.wait_for(watcher, 1)

    asyncio.run(scenario())
    assert provider.status.state == "starting" and "desapareci" in provider.status.detail


def test_manual_retry_skips_backoff(monkeypatch):
    monkeypatch.setattr(settings, "ollama_retry_min_seconds", 30)
    fake = FlakyOllama(fail_pulls=1)
    provider = OllamaProvider(url="http://ollama", transport=httpx.MockTransport(fake))

    async def scenario():
        task = asyncio.create_task(provider.ensure_ready())
        await asyncio.sleep(0.05)
        assert provider.status.state == "error" and provider.status.as_dict()["retry_in"] >= 29
        provider.request_retry()       # botón "Reintentar ahora"
        await asyncio.wait_for(task, 1)

    asyncio.run(scenario())
    assert provider.ready
