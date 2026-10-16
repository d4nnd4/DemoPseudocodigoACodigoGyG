const API = "/api";
const TO_CODE = "to_code";
const TO_PSEUDO = "to_pseudo";

const PSEUDO_EXAMPLE = `INICIO
  LEER n
  SI n < 0 ENTONCES
    IMPRIMIR "Número inválido"
    TERMINAR
  FIN SI
  suma <- 0
  PARA i DESDE 1 HASTA n HACER
    SI i MOD 2 = 0 ENTONCES
      suma <- suma + i
    FIN SI
  FIN PARA
  IMPRIMIR "La suma de los pares es: ", suma
FIN`;

const CODE_EXAMPLES = {
  python: `def suma_pares(n: int) -> int:
    suma = 0
    for i in range(1, n + 1):
        if i % 2 == 0:
            suma += i
    return suma


if __name__ == "__main__":
    n = int(input())
    if n < 0:
        print("Número inválido")
    else:
        print("La suma de los pares es:", suma_pares(n))
`,
  go: `package main

import "fmt"

func sumaPares(n int) int {
	suma := 0
	for i := 1; i <= n; i++ {
		if i%2 == 0 {
			suma += i
		}
	}
	return suma
}

func main() {
	var n int
	fmt.Scan(&n)
	if n < 0 {
		fmt.Println("Número inválido")
		return
	}
	fmt.Println("La suma de los pares es:", sumaPares(n))
}
`,
  typescript: `import * as readline from "node:readline/promises";

function sumaPares(n: number): number {
  let suma = 0;
  for (let i = 1; i <= n; i++) {
    if (i % 2 === 0) suma += i;
  }
  return suma;
}

async function main(): Promise<void> {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  const n = Number(await rl.question("n: "));
  rl.close();
  if (n < 0) {
    console.log("Número inválido");
    return;
  }
  console.log(\`La suma de los pares es: \${sumaPares(n)}\`);
}

main();
`,
  java: `import java.util.Scanner;

public class Main {
    private static int sumaPares(int n) {
        int suma = 0;
        for (int i = 1; i <= n; i++) {
            if (i % 2 == 0) suma += i;
        }
        return suma;
    }

    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        int n = sc.nextInt();
        sc.close();
        if (n < 0) {
            System.out.println("Número inválido");
            return;
        }
        System.out.println("La suma de los pares es: " + sumaPares(n));
    }
}
`,
  csharp: `using System;

class Program
{
    static int SumaPares(int n)
    {
        int suma = 0;
        for (int i = 1; i <= n; i++)
            if (i % 2 == 0) suma += i;
        return suma;
    }

    static void Main()
    {
        int n = int.Parse(Console.ReadLine() ?? "0");
        if (n < 0) { Console.WriteLine("Número inválido"); return; }
        Console.WriteLine($"La suma de los pares es: {SumaPares(n)}");
    }
}
`,
  vbnet: `Option Strict On
Option Explicit On

Module Program
    Function SumaPares(n As Integer) As Integer
        Dim suma As Integer = 0
        For i As Integer = 1 To n
            If i Mod 2 = 0 Then suma += i
        Next
        Return suma
    End Function

    Sub Main()
        Dim n As Integer = Integer.Parse(Console.ReadLine())
        If n < 0 Then
            Console.WriteLine("Número inválido")
            Return
        End If
        Console.WriteLine("La suma de los pares es: " & SumaPares(n))
    End Sub
End Module
`,
  asp: `<%@ Language="VBScript" %>
<% Option Explicit %>
<html><body>
<form method="post"><input name="n"><button>Calcular</button></form>
<%
Dim n, i, suma
If Request.Form("n") <> "" Then
  n = CInt(Request.Form("n"))
  If n < 0 Then
    Response.Write "Número inválido"
  Else
    suma = 0
    For i = 1 To n
      If i Mod 2 = 0 Then suma = suma + i
    Next
    Response.Write "La suma de los pares es: " & Server.HTMLEncode(CStr(suma))
  End If
End If
%>
</body></html>
`,
  rpgle: `**FREE
ctl-opt dftactgrp(*no) actgrp(*caller);

dcl-s n int(10) inz(10);
dcl-s i int(10);
dcl-s suma int(10) inz(0);
dcl-s msg char(52);

if n < 0;
  dsply 'Numero invalido';
  *inlr = *on;
  return;
endif;

for i = 1 to n;
  if %rem(i: 2) = 0;
    suma += i;
  endif;
endfor;

msg = 'La suma de los pares es: ' + %char(suma);
dsply msg;

*inlr = *on;
return;
`,
};

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];
const state = {
  direction: TO_CODE,
  languages: [],
  current: null,
  generating: false,
  ready: false,
  health: null,
  healthTimer: null,
  countdownTimer: null,
  config: null,
};
let inputEditor, outputEditor, monacoRef;

function toast(msg, isErr = false) {
  const el = $("#toast");
  el.textContent = msg;
  el.className = "toast show" + (isErr ? " err" : "");
  clearTimeout(el._t);
  el._t = setTimeout(() => (el.className = "toast"), 3800);
}

async function api(path, opts = {}) {
  const res = await fetch(API + path, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.status === 204 ? null : res.json();
}

const escapeHtml = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const langById = (id) => state.languages.find((l) => l.id === id);
const isExample = (text) => !text.trim() || text === PSEUDO_EXAMPLE || Object.values(CODE_EXAMPLES).includes(text);
const fmtMs = (ms) => (ms == null ? "—" : ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`);

function setActions(enabled) {
  ["#copy", "#save", "#download", "#swap"].forEach((s) => ($(s).disabled = !enabled));
}

function currentTheme() {
  const forced = document.documentElement.dataset.theme;
  if (forced) return forced;
  return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}
function applyEditorTheme() {
  if (monacoRef) monacoRef.editor.setTheme(currentTheme() === "dark" ? "gyg-dark" : "gyg-light");
}
function toggleTheme() {
  const next = currentTheme() === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  try { localStorage.setItem("p2c-theme", next); } catch {}
  applyEditorTheme();
}

function showView(name) {
  $$(".tab[data-view]").forEach((t) => t.classList.toggle("active", t.dataset.view === name));
  $$(".view").forEach((v) => (v.hidden = v.id !== `view-${name}`));
  if (name === "logs") loadLogs();
  if (name === "settings") loadConfig();
}

function editorLanguages() {
  const lang = langById($("#language").value);
  const code = lang ? lang.monaco : "plaintext";
  return state.direction === TO_CODE ? { input: "pseudo", output: code } : { input: code, output: "pseudo" };
}

function applyEditorLanguages() {
  if (!monacoRef) return;
  const langs = editorLanguages();
  monacoRef.editor.setModelLanguage(inputEditor.getModel(), langs.input);
  monacoRef.editor.setModelLanguage(outputEditor.getModel(), langs.output);
}

function exampleFor(direction, langId) {
  return direction === TO_CODE ? PSEUDO_EXAMPLE : CODE_EXAMPLES[langId] || CODE_EXAMPLES.python;
}

function setDirection(direction, { keepInput = false } = {}) {
  state.direction = direction;
  const toCode = direction === TO_CODE;
  $$(".segmented button").forEach((b) => b.classList.toggle("active", b.dataset.direction === direction));
  $("#input-title").textContent = toCode ? "Pseudocódigo" : "Código fuente";
  $("#language-label").textContent = toCode ? "Destino" : "Origen";
  if (!state.generating && !state.current) $("#output-title").textContent = toCode ? "Código generado" : "Pseudocódigo generado";
  if (!keepInput && isExample(inputEditor.getValue())) inputEditor.setValue(exampleFor(direction, $("#language").value));
  applyEditorLanguages();
  updateConvertButton();
}

function onLanguageChange() {
  const lang = langById($("#language").value);
  const note = $("#lang-note");
  note.hidden = !lang?.note;
  note.textContent = lang?.note || "";
  // En código -> pseudocódigo, si la entrada es un ejemplo, cambiarlo al del nuevo lenguaje.
  if (state.direction === TO_PSEUDO && isExample(inputEditor.getValue())) inputEditor.setValue(exampleFor(TO_PSEUDO, lang?.id));
  if (!state.current) applyEditorLanguages();
}

function updateConvertButton() {
  const btn = $("#convert");
  if (state.generating) return;
  btn.disabled = !state.ready;
  btn.textContent = state.ready ? (state.direction === TO_CODE ? "Generar código ▶" : "Explicar en pseudocódigo ▶") : "Esperando modelo…";
  btn.title = state.ready ? "Ctrl/Cmd + Enter" : state.health?.detail || "";
}

function renderBanner() {
  const h = state.health;
  const banner = $("#model-banner");
  if (h && h.state === "ready") {
    banner.hidden = true;
    clearInterval(state.countdownTimer);
    return;
  }
  banner.hidden = false;
  const title = $("#banner-title");
  const detail = $("#banner-detail");
  const bar = $("#banner-progress");
  bar.hidden = true;
  $("#banner-retry").hidden = h && (h.state === "pulling" || h.state === "loading");

  if (!h) {
    banner.className = "banner err";
    title.textContent = "No se puede contactar con la API.";
    detail.textContent = "Reintentando cada 2 s…";
    return;
  }
  const model = h.model;
  if (h.state === "pulling") {
    banner.className = "banner info";
    title.textContent = `Descargando ${model} · ${Math.floor(h.progress ?? 0)} %`;
    detail.textContent = "La conversión se habilita sola cuando el modelo esté disponible localmente.";
    bar.hidden = false;
    bar.value = h.progress ?? 0;
  } else if (h.state === "loading") {
    banner.className = "banner info";
    title.textContent = h.detail;
    detail.textContent = "Casi listo.";
  } else {
    banner.className = h.state === "error" ? "banner" : "banner info";
    title.textContent = h.state === "error" ? `${model} aún no está disponible localmente.` : h.detail;
    const parts = [];
    if (h.last_error) parts.push(`Motivo: ${h.last_error}.`);
    if (h.attempt) parts.push(`Intento ${h.attempt}.`);
    if (h.retry_in != null) parts.push(`<span id="retry-countdown">Reintento automático en ${h.retry_in} s.</span>`);
    detail.innerHTML = parts.map((p) => (p.startsWith("<span") ? p : escapeHtml(p))).join(" ");
    startCountdown(h.retry_in);
  }
}

function startCountdown(seconds) {
  clearInterval(state.countdownTimer);
  if (seconds == null) return;
  let left = seconds;
  state.countdownTimer = setInterval(() => {
    left = Math.max(0, left - 1);
    const el = $("#retry-countdown");
    if (el) el.textContent = left > 0 ? `Reintento automático en ${left} s.` : "Reintentando…";
  }, 1000);
}

async function checkHealth() {
  const el = $("#status");
  const text = el.querySelector(".status-text");
  try {
    const h = await api("/health");
    state.health = h;
    state.ready = h.state === "ready";
    el.className = "status " + (state.ready ? "ok" : h.state === "error" ? "err" : "busy");
    text.textContent = state.ready ? `${h.provider} · ${h.model}` : h.state === "pulling" ? `Descargando · ${Math.floor(h.progress ?? 0)} %` : "Modelo no disponible";
    el.title = h.detail;
  } catch {
    state.health = null;
    state.ready = false;
    el.className = "status err";
    text.textContent = "API no disponible";
  }
  renderBanner();
  updateConvertButton();
  clearTimeout(state.healthTimer);
  state.healthTimer = setTimeout(checkHealth, state.ready ? 30000 : 2000);
}

async function retryModel() {
  try {
    await api("/model/retry", { method: "POST" });
    toast("Reintentando preparar el modelo…");
    setTimeout(checkHealth, 400);
  } catch (e) {
    toast(e.message, true);
  }
}

async function loadHistory() {
  const list = $("#history-list");
  const items = await api("/history").catch(() => []);
  list.innerHTML = "";
  if (!items.length) {
    list.innerHTML = '<li class="empty">Aún no hay conversiones.</li>';
    return;
  }
  for (const it of items) {
    const li = document.createElement("li");
    li.dataset.id = it.id;
    if (state.current && state.current.id === it.id) li.classList.add("active");
    const date = new Date(it.created_at).toLocaleString();
    const dir = it.direction === TO_PSEUDO ? "→ pseudo" : "→ código";
    li.innerHTML = `
      <div class="meta">
        <div class="title"></div>
        <div class="sub"><span class="tag">${escapeHtml(it.language)}</span><span class="tag dir">${dir}</span><br>${date}</div>
      </div>
      <button class="del" title="Eliminar">✕</button>`;
    li.querySelector(".title").textContent = it.name;
    li.addEventListener("click", () => openItem(it.id));
    li.querySelector(".del").addEventListener("click", async (e) => {
      e.stopPropagation();
      if (!confirm(`¿Eliminar "${it.name}"?`)) return;
      await api(`/history/${it.id}`, { method: "DELETE" });
      if (state.current && state.current.id === it.id) clearOutput();
      loadHistory();
    });
    list.appendChild(li);
  }
}

async function openItem(id) {
  try {
    const item = await api(`/history/${id}`);
    $("#language").value = item.language;
    onLanguageChange();
    setDirection(item.direction, { keepInput: true });
    inputEditor.setValue(item.input);
    $("#name").value = item.name;
    showItem(item);
    $("#run-info").textContent = `${item.model} · ${new Date(item.updated_at).toLocaleString()}`;
    loadHistory();
  } catch (e) {
    toast(e.message, true);
  }
}

function showItem(item) {
  state.current = item;
  applyEditorLanguages();
  outputEditor.setValue(item.output);
  const root = state.config?.paths?.generated_host_dir || "generated";
  $("#saved-path").textContent = `${root.replace(/\/$/, "")}/${item.path}`;
  $("#saved-path").title = $("#saved-path").textContent;
  $("#output-title").textContent = item.name;
  setActions(true);
}

function clearOutput() {
  state.current = null;
  outputEditor.setValue("");
  $("#saved-path").textContent = "";
  $("#run-info").textContent = "";
  $("#output-title").textContent = state.direction === TO_CODE ? "Código generado" : "Pseudocódigo generado";
  setActions(false);
}

function appendToOutput(text) {
  const model = outputEditor.getModel();
  const line = model.getLineCount();
  const col = model.getLineMaxColumn(line);
  model.applyEdits([{ range: new monacoRef.Range(line, col, line, col), text }]);
  const last = model.getLineCount();
  outputEditor.setPosition({ lineNumber: last, column: model.getLineMaxColumn(last) });
  outputEditor.revealLine(last);
}

async function convert() {
  if (!state.ready) return toast(state.health?.detail || "El modelo aún no está listo", true);
  const source = inputEditor.getValue().trim();
  if (source.length < 3) return toast("Escribe algo en la entrada primero", true);
  const language = $("#language").value;
  const direction = state.direction;

  state.generating = true;
  clearOutput();
  const btn = $("#convert");
  btn.disabled = true;
  btn.textContent = "Generando…";
  applyEditorLanguages();
  $("#output-title").textContent = "Generando…";
  $(".output").classList.add("streaming");

  const t0 = performance.now();
  let chunks = 0;
  const tick = setInterval(() => {
    $("#run-info").textContent = `${chunks} fragmentos · ${((performance.now() - t0) / 1000).toFixed(1)} s`;
  }, 200);

  let buffer = "";
  try {
    const res = await fetch(`${API}/convert`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ direction, source, language, name: $("#name").value.trim() || null }),
    });
    if (!res.ok) {
      if (res.status === 503) checkHealth();
      throw new Error((await res.json().catch(() => ({}))).detail || `HTTP ${res.status}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let nl;
      while ((nl = buffer.indexOf("\n")) >= 0) {
        const line = buffer.slice(0, nl).trim();
        buffer = buffer.slice(nl + 1);
        if (!line) continue;
        const ev = JSON.parse(line);
        if (ev.type === "queued") {
          $("#output-title").textContent = "En cola…";
        } else if (ev.type === "token") {
          if (!chunks) $("#output-title").textContent = "Generando…";
          chunks++;
          appendToOutput(ev.content);
        } else if (ev.type === "done") {
          clearInterval(tick);
          showItem(ev.item);
          const secs = ((performance.now() - t0) / 1000).toFixed(1);
          $("#run-info").textContent = `${ev.item.model} · ${secs} s · req ${ev.request_id}`;
          toast(`Guardado en ${$("#saved-path").textContent}`);
          loadHistory();
        } else if (ev.type === "error") {
          throw new Error(ev.message);
        }
      }
    }
  } catch (e) {
    $("#output-title").textContent = direction === TO_CODE ? "Código generado" : "Pseudocódigo generado";
    $("#run-info").textContent = "";
    toast(e.message, true);
  } finally {
    clearInterval(tick);
    $(".output").classList.remove("streaming");
    state.generating = false;
    updateConvertButton();
  }
}

async function saveEdits() {
  if (!state.current) return;
  try {
    state.current = await api(`/history/${state.current.id}`, {
      method: "PUT",
      body: JSON.stringify({ output: outputEditor.getValue() }),
    });
    toast("Cambios guardados");
  } catch (e) {
    toast(e.message, true);
  }
}

function swapDirection() {
  const output = outputEditor.getValue();
  if (!output.trim()) return;
  inputEditor.setValue(output);
  $("#name").value = "";
  clearOutput();
  setDirection(state.direction === TO_CODE ? TO_PSEUDO : TO_CODE, { keepInput: true });
}

async function loadLogs() {
  const params = new URLSearchParams({ limit: "300" });
  if ($("#log-event").value) params.set("event", $("#log-event").value);
  if ($("#log-status").value) params.set("status", $("#log-status").value);
  const rows = await api(`/logs?${params}`).catch((e) => (toast(e.message, true), []));

  const conv = rows.filter((r) => r.event === "convert");
  const ok = conv.filter((r) => r.status === "ok");
  const avg = ok.length ? Math.round(ok.reduce((a, r) => a + (r.duration_ms || 0), 0) / ok.length) : null;
  const ttft = ok.filter((r) => r.ttft_ms != null);
  const avgTtft = ttft.length ? Math.round(ttft.reduce((a, r) => a + r.ttft_ms, 0) / ttft.length) : null;
  const stats = [
    ["Conversiones", conv.length],
    ["Exitosas", conv.length ? `${Math.round((100 * ok.length) / conv.length)} %` : "—"],
    ["Con error", conv.filter((r) => r.status === "error").length],
    ["Duración media", fmtMs(avg)],
    ["1.er token medio", fmtMs(avgTtft)],
  ];
  $("#log-stats").innerHTML = stats
    .map(([l, v]) => `<div class="stat"><div class="label">${l}</div><div class="value">${v}</div></div>`)
    .join("");

  const tbody = $("#log-rows");
  if (!rows.length) {
    tbody.innerHTML = '<tr><td colspan="11" class="muted">Sin registros todavía.</td></tr>';
    return;
  }
  tbody.innerHTML = rows
    .map((r) => {
      const dir = r.direction === TO_PSEUDO ? "código → pseudo" : r.direction === TO_CODE ? "pseudo → código" : "—";
      const file = r.error
        ? `<span class="err-msg">${escapeHtml(r.error)}</span>`
        : escapeHtml(r.path || "");
      const io = r.input_chars != null ? `${r.input_chars} / ${r.output_chars ?? "—"}` : r.output_chars ?? "—";
      return `<tr>
        <td>${new Date(r.ts).toLocaleString()}</td>
        <td>${escapeHtml(r.event)}</td>
        <td><span class="pill ${escapeHtml(r.status)}">${escapeHtml(r.status)}</span></td>
        <td>${dir}</td>
        <td>${escapeHtml(r.language || "—")}</td>
        <td>${escapeHtml(r.model || "—")}</td>
        <td class="num">${fmtMs(r.queued_ms)}</td>
        <td class="num">${fmtMs(r.ttft_ms)}</td>
        <td class="num">${fmtMs(r.duration_ms)}</td>
        <td class="num">${io}</td>
        <td class="file" title="${escapeHtml(r.error || r.path || "")}">${file}${r.request_id ? ` <span class="muted">· ${escapeHtml(r.request_id)}</span>` : ""}</td>
      </tr>`;
    })
    .join("");
}

function kv(el, pairs) {
  el.innerHTML = pairs.map(([k, v]) => `<dt>${escapeHtml(k)}</dt><dd>${escapeHtml(v || "—")}</dd>`).join("");
}

function previewPath(template, ext, langId) {
  const now = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  const vals = {
    language: langId, direction: "", id: "3f9a1c2b7e", slug: "suma_de_pares",
    date: `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`,
    year: String(now.getFullYear()), month: pad(now.getMonth() + 1),
  };
  return template.replace(/\{(\w+)\}/g, (_, k) => vals[k] ?? `{${k}}`) + "." + ext;
}

async function loadConfig() {
  try {
    const cfg = await api("/config");
    state.config = cfg;
    const h = state.health;
    kv($("#cfg-model"), [
      ["Proveedor", cfg.provider],
      ["Modelo", cfg.model],
      ["Estado", h ? `${h.state} — ${h.detail}` : "API no disponible"],
      ["Disponibles", cfg.providers.join(", ")],
      ["Conversiones simultáneas", String(cfg.max_concurrent_generations)],
      ["Tope de salida", `${cfg.llm_max_tokens} tokens`],
    ]);
    const p = cfg.paths;
    kv($("#cfg-paths"), [
      ["Archivos (host)", p.generated_host_dir],
      ["Logs (host)", p.logs_host_dir],
      ["CODE_PATH_TEMPLATE", p.code_path_template],
      ["PSEUDO_PATH_TEMPLATE", p.pseudo_path_template],
      ["Variables", p.template_fields.map((f) => `{${f}}`).join(" ")],
    ]);
    const root = (p.generated_host_dir || "generated").replace(/\/$/, "");
    $("#cfg-preview").textContent =
      `${root}/${previewPath(p.code_path_template, "go", "go")}\n` +
      `${root}/${previewPath(p.pseudo_path_template, p.pseudo_extension, "go")}`;
  } catch (e) {
    toast(e.message, true);
  }
}

function renderLearn() {
  const categories = ["Todos", ...new Set(window.DSA.map((d) => d.category))];
  let active = "Todos";
  const filters = $("#dsa-filters");
  filters.innerHTML = categories.map((c) => `<button class="chip${c === active ? " active" : ""}" data-cat="${escapeHtml(c)}">${escapeHtml(c)}</button>`).join("");

  const langOptions = state.languages.map((l) => `<option value="${l.id}">${escapeHtml(l.label)}</option>`).join("");
  const grid = $("#dsa-grid");

  function draw() {
    const q = $("#dsa-search").value.trim().toLowerCase();
    const items = window.DSA.filter((d) =>
      (active === "Todos" || d.category === active) &&
      (!q || `${d.name} ${d.when} ${d.category}`.toLowerCase().includes(q)));
    grid.innerHTML = items.map((d, i) => `
      <article class="card">
        <div class="card-head"><h3>${escapeHtml(d.name)}</h3><span class="complexity">${escapeHtml(d.complexity)}</span></div>
        <p><span class="tag">${escapeHtml(d.category)}</span></p>
        <p class="when">${escapeHtml(d.when)}</p>
        <pre class="snippet">${escapeHtml(d.pseudo)}</pre>
        <div class="card-actions">
          <select data-idx="${window.DSA.indexOf(d)}">${langOptions}</select>
          <button class="primary small" data-convert="${window.DSA.indexOf(d)}">Convertir</button>
          <button class="small" data-copy="${window.DSA.indexOf(d)}">Copiar</button>
        </div>
      </article>`).join("") || '<p class="muted">Nada coincide con la búsqueda.</p>';
  }

  filters.addEventListener("click", (e) => {
    const cat = e.target.dataset?.cat;
    if (!cat) return;
    active = cat;
    $$("#dsa-filters .chip").forEach((c) => c.classList.toggle("active", c.dataset.cat === cat));
    draw();
  });
  $("#dsa-search").addEventListener("input", draw);
  grid.addEventListener("click", async (e) => {
    const conv = e.target.dataset?.convert;
    const copy = e.target.dataset?.copy;
    if (conv != null) {
      const d = window.DSA[conv];
      const lang = grid.querySelector(`select[data-idx="${conv}"]`).value;
      showView("convert");
      clearOutput();
      $("#language").value = lang;
      onLanguageChange();
      setDirection(TO_CODE, { keepInput: true });
      inputEditor.setValue(d.pseudo);
      $("#name").value = d.name;
      if (state.ready) convert();
      else toast("El pseudocódigo quedó en el conversor; se podrá generar cuando el modelo esté listo.");
    } else if (copy != null) {
      await navigator.clipboard.writeText(window.DSA[copy].pseudo);
      toast("Pseudocódigo copiado");
    }
  });
  draw();

  $("#docs-grid").innerHTML = window.LANGUAGE_DOCS.map((l) => `
    <article class="card">
      <h3>${escapeHtml(l.name)}</h3>
      ${l.links.map(([t, u]) => `<a href="${u}" target="_blank" rel="noopener">${escapeHtml(t)} ↗</a>`).join("")}
    </article>`).join("");
  $("#extra-resources").innerHTML = window.EXTRA_RESOURCES.map(([t, u, d]) =>
    `<li><a href="${u}" target="_blank" rel="noopener">${escapeHtml(t)}</a> <span class="muted">— ${escapeHtml(d)}</span></li>`).join("");
}

require.config({ paths: { vs: "vendor/monaco/vs" } });
require(["vs/editor/editor.main"], async () => {
  monacoRef = monaco;
  window.registerExtraLanguages(monaco);

  const common = {
    theme: currentTheme() === "dark" ? "gyg-dark" : "gyg-light",
    automaticLayout: true,
    minimap: { enabled: false },
    fontSize: 14,
    scrollBeyondLastLine: false,
    stickyScroll: { enabled: false },
    padding: { top: 8 },
    fontFamily: 'ui-monospace, "Cascadia Code", "JetBrains Mono", Consolas, monospace',
  };
  inputEditor = monaco.editor.create($("#input-editor"), { ...common, language: "pseudo", value: PSEUDO_EXAMPLE, wordWrap: "on" });
  outputEditor = monaco.editor.create($("#output-editor"), { ...common, language: "python", value: "" });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", applyEditorTheme);

  inputEditor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => !state.generating && convert());
  outputEditor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, saveEdits);

  state.languages = await api("/languages").catch(() => []);
  $("#language").innerHTML = state.languages.map((l) => `<option value="${l.id}">${escapeHtml(l.label)}</option>`).join("");
  $("#language").addEventListener("change", onLanguageChange);
  onLanguageChange();
  applyEditorLanguages();

  $$(".tab[data-view]").forEach((t) => t.addEventListener("click", () => showView(t.dataset.view)));
  $$(".segmented button").forEach((b) => b.addEventListener("click", () => {
    if (state.generating || b.dataset.direction === state.direction) return;
    clearOutput();
    setDirection(b.dataset.direction);
  }));
  $("#convert").addEventListener("click", convert);
  $("#example").addEventListener("click", () => inputEditor.setValue(exampleFor(state.direction, $("#language").value)));
  $("#refresh").addEventListener("click", loadHistory);
  $("#save").addEventListener("click", saveEdits);
  $("#swap").addEventListener("click", swapDirection);
  $("#copy").addEventListener("click", async () => {
    await navigator.clipboard.writeText(outputEditor.getValue());
    toast("Copiado al portapapeles");
  });
  $("#download").addEventListener("click", () => {
    if (state.current) window.location.href = `${API}/history/${state.current.id}/download`;
  });
  $("#banner-retry").addEventListener("click", retryModel);
  $("#cfg-retry").addEventListener("click", retryModel);
  $("#theme-toggle").addEventListener("click", toggleTheme);
  $("#log-refresh").addEventListener("click", loadLogs);
  $("#log-event").addEventListener("change", loadLogs);
  $("#log-status").addEventListener("change", loadLogs);

  setDirection(TO_CODE, { keepInput: true });
  renderLearn();
  api("/config").then((c) => (state.config = c)).catch(() => {});
  checkHealth();
  loadHistory();
});
