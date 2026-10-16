"""Prueba de carga mínima para dimensionar el servidor (ver docs/ESCALABILIDAD.md, sección 6).

Lanza --requests conversiones contra /api/convert con --concurrency en paralelo y reporta el
tiempo al primer token (TTFT) y la duración total, P50 / P95.

    pip install httpx
    python scripts/loadtest.py --url http://localhost:8080 --concurrency 12 --requests 36

Ojo: cada conversión queda guardada en el historial y en los logs del servidor.
"""

import argparse
import asyncio
import json
import statistics
import time

import httpx

PSEUDO = """INICIO
  LEER n
  suma <- 0
  PARA i DESDE 1 HASTA n HACER
    SI i MOD 2 = 0 ENTONCES
      suma <- suma + i
    FIN SI
  FIN PARA
  IMPRIMIR "La suma de los pares es: ", suma
FIN"""


async def one(client: httpx.AsyncClient, language: str) -> dict:
    t0 = time.perf_counter()
    ttft = None
    chunks = 0
    body = {"direction": "to_code", "source": PSEUDO, "language": language, "name": "loadtest"}
    async with client.stream("POST", "/api/convert", json=body) as resp:
        if resp.status_code != 200:
            return {"ok": False, "error": f"HTTP {resp.status_code}"}
        async for line in resp.aiter_lines():
            if not line.strip():
                continue
            ev = json.loads(line)
            if ev["type"] == "token":
                ttft = ttft or time.perf_counter() - t0
                chunks += 1
            elif ev["type"] == "error":
                return {"ok": False, "error": ev["message"]}
    return {"ok": True, "ttft": ttft or 0.0, "total": time.perf_counter() - t0, "chunks": chunks}


def pct(values: list[float], p: float) -> float:
    if not values:
        return float("nan")
    values = sorted(values)
    return values[min(len(values) - 1, int(round(p / 100 * (len(values) - 1))))]


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8080")
    ap.add_argument("--concurrency", type=int, default=12)
    ap.add_argument("--requests", type=int, default=36)
    ap.add_argument("--language", default="python")
    args = ap.parse_args()

    sem = asyncio.Semaphore(args.concurrency)
    async with httpx.AsyncClient(base_url=args.url, timeout=httpx.Timeout(900, connect=10)) as client:
        async def guarded():
            async with sem:
                return await one(client, args.language)

        t0 = time.perf_counter()
        results = await asyncio.gather(*(guarded() for _ in range(args.requests)))
        wall = time.perf_counter() - t0

    ok = [r for r in results if r["ok"]]
    errors = [r["error"] for r in results if not r["ok"]]
    ttft = [r["ttft"] for r in ok]
    total = [r["total"] for r in ok]
    print(f"Peticiones: {len(results)}  ok: {len(ok)}  errores: {len(errors)}  "
          f"concurrencia: {args.concurrency}  tiempo total: {wall:.1f} s")
    if ok:
        print(f"TTFT      P50 {pct(ttft, 50):6.2f} s   P95 {pct(ttft, 95):6.2f} s")
        print(f"Duración  P50 {pct(total, 50):6.2f} s   P95 {pct(total, 95):6.2f} s   "
              f"media {statistics.mean(total):.2f} s")
        print(f"Throughput: {len(ok) / wall:.2f} conversiones/s")
    for e in sorted(set(errors))[:5]:
        print("  error:", e)


if __name__ == "__main__":
    asyncio.run(main())
