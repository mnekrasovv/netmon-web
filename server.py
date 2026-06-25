#!/usr/bin/env python3
"""netmon-web — FastAPI server + SSE streams + static SPA."""

from __future__ import annotations

import asyncio
import json
import threading
import time
import webbrowser
from pathlib import Path
from typing import Iterator, Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from core import batch, dns_check, hosts, http_check, ping, reports, sysinfo, trace

ROOT = Path(__file__).parent
STATIC_DIR = ROOT / "static"

app = FastAPI(title="netmon-web")

# ── SSE helpers ──────────────────────────────────────────────────────────────────

async def sse_from_sync(sync_gen: Iterator, mapper=None):
    """Wrap a sync generator into an async SSE response (running in executor)."""
    loop = asyncio.get_event_loop()
    _SENTINEL = object()

    def next_or_stop(it):
        try:
            return next(it)
        except StopIteration:
            return _SENTINEL

    while True:
        item = await loop.run_in_executor(None, next_or_stop, sync_gen)
        if item is _SENTINEL:
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return
        event = mapper(item) if mapper else {"type": "line", "payload": item}
        yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def sse_response(generator) -> StreamingResponse:
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Static ───────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def root():
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── REST: hosts ──────────────────────────────────────────────────────────────────

@app.get("/api/hosts")
def api_hosts_list():
    return {"hosts": hosts.list_hosts()}


@app.post("/api/hosts")
async def api_hosts_add(request: Request):
    data = await request.json()
    h = (data.get("host") or "").strip()
    if not h:
        raise HTTPException(400, "host required")
    n = (data.get("name") or "").strip()
    c = (data.get("cat") or "custom").strip()
    return hosts.add_host(h, n, c)


@app.delete("/api/hosts/{idx}")
def api_hosts_delete(idx: int):
    if not hosts.delete_host(idx):
        raise HTTPException(404, "not found")
    return {"ok": True}


@app.put("/api/hosts/{idx}")
async def api_hosts_update(idx: int, request: Request):
    data = await request.json()
    h = (data.get("host") or "").strip()
    n = (data.get("name") or "").strip()
    c = (data.get("cat") or "custom").strip()
    if not h:
        raise HTTPException(400, "host required")
    if not hosts.update_host(idx, h, n, c):
        raise HTTPException(404, "not found")
    return {"ok": True}


# ── REST: sysinfo / gateway ──────────────────────────────────────────────────────

@app.get("/api/sysinfo")
def api_sysinfo():
    return sysinfo.sysinfo()


@app.get("/api/gateway")
def api_gateway():
    return {"gateway": ping.get_gateway()}


# ── REST: external IP ────────────────────────────────────────────────────────────

@app.get("/api/external-ip")
def api_external_ip():
    return http_check.external_ip()


# ── REST: DNS ────────────────────────────────────────────────────────────────────

@app.get("/api/dns/matrix")
def api_dns_matrix():
    return dns_check.dns_matrix()


@app.get("/api/dns/pings")
def api_dns_pings():
    return {"pings": dns_check.dns_server_pings()}


# ── REST: sites (batch) ──────────────────────────────────────────────────────────

@app.get("/api/sites")
def api_sites():
    cfg = batch.load_sites()
    cats = []
    for cat, sites in cfg.get("categories", {}).items():
        cats.append({"name": cat, "count": len(sites)})
    return {"categories": cats}


# ── REST: reports ────────────────────────────────────────────────────────────────

@app.get("/api/reports")
def api_reports_list():
    return {"reports": reports.list_reports()}


@app.get("/api/reports/{name}")
def api_reports_read(name: str):
    try:
        content = reports.read_report(name)
    except FileNotFoundError:
        raise HTTPException(404, "not found")
    if name.endswith(".json"):
        return JSONResponse(json.loads(content))
    if name.endswith(".html"):
        return HTMLResponse(content)
    return PlainTextResponse(content)


@app.get("/api/reports/{name}/download")
def api_reports_download(name: str):
    p = reports.REPORTS_DIR / name
    if not p.exists() or "/" in name or "\\" in name or ".." in name:
        raise HTTPException(404, "not found")
    return FileResponse(str(p), filename=name)


@app.delete("/api/reports/{name}")
def api_reports_delete(name: str):
    if not reports.delete_report(name):
        raise HTTPException(404, "not found")
    return {"ok": True}


# ── REST: save report from buffer ────────────────────────────────────────────────

@app.post("/api/reports/save")
async def api_reports_save(request: Request):
    data = await request.json()
    prefix = (data.get("prefix") or "report").strip()
    lines = data.get("lines") or []
    if not isinstance(lines, list):
        raise HTTPException(400, "lines must be list")
    name = reports.save_text(prefix, lines)
    return {"name": name}


@app.post("/api/reports/save-batch-html")
async def api_reports_save_batch_html(request: Request):
    data = await request.json()
    summary = data.get("summary")
    if not summary:
        raise HTTPException(400, "summary required")
    name = reports.save_html_batch(summary)
    json_name = reports.save_json("batch", summary)
    return {"html": name, "json": json_name}


# ── SSE streams ──────────────────────────────────────────────────────────────────

@app.get("/api/stream/ping")
async def stream_ping(host: str, count: int = 10):
    return sse_response(sse_from_sync(ping.ping_stream(host, count)))


@app.get("/api/stream/trace")
async def stream_trace(host: str):
    return sse_response(sse_from_sync(trace.trace_stream(host)))


@app.get("/api/stream/mtr")
async def stream_mtr(host: str, cycles: int = 10):
    return sse_response(sse_from_sync(trace.mtr_stream(host, cycles)))


@app.get("/api/stream/http")
async def stream_http(url: str, timeout: int = 10):
    return sse_response(sse_from_sync(http_check.http_check_stream(url, timeout)))


@app.get("/api/stream/dns")
async def stream_dns():
    return sse_response(sse_from_sync(dns_check.dns_stream()))


@app.get("/api/stream/external-ip")
async def stream_external_ip():
    return sse_response(sse_from_sync(http_check.external_ip_stream()))


@app.get("/api/stream/sysinfo")
async def stream_sysinfo():
    return sse_response(sse_from_sync(sysinfo.sysinfo_stream()))


@app.get("/api/stream/interfaces")
async def stream_interfaces():
    return sse_response(sse_from_sync(sysinfo.interfaces_stream()))


@app.get("/api/stream/connections")
async def stream_connections():
    return sse_response(sse_from_sync(sysinfo.connections_stream()))


@app.get("/api/stream/arp")
async def stream_arp():
    return sse_response(sse_from_sync(sysinfo.arp_stream()))


# ── SSE: batch monitor (sends structured events, not lines) ──────────────────────

@app.get("/api/stream/batch")
async def stream_batch(
    categories: Optional[str] = Query(None, description="comma-separated"),
    ping_count: int = 10,
    workers: int = 20,
    no_http: bool = False,
    http_timeout: int = 10,
):
    cats = [c.strip() for c in categories.split(",")] if categories else None
    gen = batch.batch_check_stream(
        categories=cats,
        ping_count=ping_count,
        workers=workers,
        no_http=no_http,
        http_timeout=http_timeout,
    )
    return sse_response(sse_from_sync(gen, mapper=lambda x: x))


# ── Entry point ──────────────────────────────────────────────────────────────────

def _open_browser_delayed(url: str, delay: float = 1.2):
    def _open():
        time.sleep(delay)
        try:
            webbrowser.open(url)
        except Exception:
            pass
    threading.Thread(target=_open, daemon=True).start()


def main():
    import argparse
    import uvicorn

    ap = argparse.ArgumentParser(description="netmon-web server")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true", help="не открывать браузер автоматически")
    args = ap.parse_args()

    url = f"http://{args.host}:{args.port}"
    print(f"\n  netmon-web → {url}\n")
    if not args.no_browser:
        _open_browser_delayed(url)
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
