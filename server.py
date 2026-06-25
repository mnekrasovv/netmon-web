#!/usr/bin/env python3
"""netmon-web — FastAPI server + SSE streams + static SPA."""

from __future__ import annotations

import asyncio
import json
import os
import platform
import subprocess
import threading
import time
import webbrowser
from pathlib import Path
from typing import Iterator, Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from core import (
    batch, dns_check, hosts, http_check, live_dashboard, lookup, parsers,
    ping, reports, sites, suggestions, sysinfo, tcp_check, trace,
)
from core.runner import IS_WINDOWS, has, run_cmd

ROOT = Path(__file__).parent
STATIC_DIR = ROOT / "static"
VERSION_FILE = ROOT / "VERSION"

try:
    APP_VERSION = VERSION_FILE.read_text(encoding="utf-8").strip()
except Exception:
    APP_VERSION = "dev"

GITHUB_LATEST_API = "https://api.github.com/repos/mnekrasovv/netmon-web/releases/latest"
GITHUB_RELEASES_URL = "https://github.com/mnekrasovv/netmon-web/releases"

app = FastAPI(title="netmon-web")


# ── SSE helpers ──────────────────────────────────────────────────────────────────

async def sse_from_sync(sync_gen: Iterator, mapper=None):
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


# ── REST: sysinfo ────────────────────────────────────────────────────────────────

@app.get("/api/sysinfo")
def api_sysinfo():
    return sysinfo.sysinfo()


@app.get("/api/gateway")
def api_gateway():
    return {"gateway": ping.get_gateway()}


@app.get("/api/external-ip")
def api_external_ip():
    return http_check.external_ip()


# ── REST: parsed diagnostics ─────────────────────────────────────────────────────

@app.get("/api/parsed/ping")
def api_parsed_ping(host: str, count: int = 10):
    if IS_WINDOWS:
        cmd = ["ping", "-n", str(count), "-w", "1500", host]
    else:
        cmd = ["ping", "-c", str(count), "-W", "2", "-i", "0.5", host]
    out = run_cmd(cmd, timeout=count * 3 + 10)
    return {"raw": out, "parsed": parsers.parse_ping(out, host, count)}


@app.get("/api/parsed/trace")
def api_parsed_trace(host: str):
    if IS_WINDOWS:
        cmd = ["tracert", "-d", host]
    elif has("traceroute"):
        cmd = ["traceroute", "-n", "-w", "3", "-m", "30", host]
    elif has("tracepath"):
        cmd = ["tracepath", "-n", host]
    else:
        return {"raw": "", "parsed": [], "error": "traceroute not available"}
    out = run_cmd(cmd, timeout=180)
    return {"raw": out, "parsed": parsers.parse_traceroute(out)}


@app.get("/api/parsed/mtr")
def api_parsed_mtr(host: str, cycles: int = 10):
    """Pure-python MTR returns structured hops."""
    # Get trace first
    if IS_WINDOWS:
        trace_out = run_cmd(["tracert", "-d", host], timeout=120)
    elif has("traceroute"):
        trace_out = run_cmd(["traceroute", "-n", "-w", "2", "-m", "30", host], timeout=120)
    elif has("tracepath"):
        trace_out = run_cmd(["tracepath", "-n", host], timeout=120)
    else:
        return {"hops": [], "error": "traceroute not available"}

    trace_hops = parsers.parse_traceroute(trace_out)
    seen = set()
    structured_hops = []
    for h in trace_hops:
        ip = h.get("ip")
        if not ip:
            structured_hops.append({
                "hop": h["hop"], "ip": None, "timeout": True,
                "loss": 100.0, "avg": None, "min": None, "max": None,
                "sent": 0, "recv": 0,
            })
            continue
        if ip in seen:
            continue
        seen.add(ip)
        stats = ping.ping_stats(ip, count=cycles, fast=True)
        structured_hops.append({
            "hop": h["hop"],
            "ip": ip,
            "timeout": False,
            "loss": stats["loss"],
            "avg": stats["avg"],
            "min": stats["min"],
            "max": stats["max"],
            "sent": stats["sent"],
            "recv": stats["recv"],
        })

    return {"target": host, "hops": structured_hops}


@app.get("/api/parsed/http")
def api_parsed_http(url: str, timeout: int = 10):
    return http_check.http_check(url, timeout)


@app.get("/api/parsed/interfaces")
def api_parsed_interfaces():
    if IS_WINDOWS:
        out = run_cmd(["ipconfig", "/all"], timeout=15)
    elif has("ip"):
        out = run_cmd(["ip", "addr", "show"], timeout=10)
    elif has("ifconfig"):
        out = run_cmd(["ifconfig", "-a"], timeout=10)
    else:
        return {"interfaces": [], "raw": ""}
    return {"raw": out, "interfaces": parsers.parse_interfaces(out)}


@app.get("/api/parsed/connections")
def api_parsed_connections():
    if not IS_WINDOWS and has("ss"):
        out = run_cmd(["ss", "-tunlp"], timeout=10)
        rows = parsers.parse_connections_ss(out)
    else:
        out = run_cmd(["netstat", "-an"], timeout=15)
        rows = parsers.parse_connections_netstat(out)
    return {"raw": out, "connections": rows}


# ── REST: DNS ────────────────────────────────────────────────────────────────────

@app.get("/api/dns/matrix")
def api_dns_matrix():
    return dns_check.dns_matrix()


@app.get("/api/dns/pings")
def api_dns_pings():
    return {"pings": dns_check.dns_server_pings()}


# ── REST: tools (tcp / whois / nslookup) ─────────────────────────────────────────

@app.get("/api/tcp")
def api_tcp(host: str, ports: str = Query(..., description="comma-separated"), timeout: float = 3.0):
    plist = []
    for p in ports.split(","):
        p = p.strip()
        if not p:
            continue
        if p.lower() in tcp_check.PORT_PRESETS:
            plist.append(tcp_check.PORT_PRESETS[p.lower()])
        else:
            try:
                plist.append(int(p))
            except ValueError:
                pass
    if not plist:
        raise HTTPException(400, "no valid ports")
    return {"host": host, "results": tcp_check.check_ports(host, plist, timeout)}


@app.get("/api/tcp/presets")
def api_tcp_presets():
    return tcp_check.PORT_PRESETS


@app.get("/api/whois")
def api_whois(host: str):
    return lookup.whois(host)


@app.get("/api/nslookup")
def api_nslookup(host: str, server: str = "", type: str = "A"):
    return lookup.nslookup(host, server, type)


# ── REST: sites (full CRUD) ──────────────────────────────────────────────────────

@app.get("/api/sites")
def api_sites_summary():
    return sites.get_summary()


@app.get("/api/sites/all")
def api_sites_all():
    return sites.get_all()


@app.post("/api/sites/categories")
async def api_sites_add_cat(request: Request):
    data = await request.json()
    name = (data.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "name required")
    if not sites.add_category(name):
        raise HTTPException(409, "category exists or invalid")
    return {"ok": True}


@app.delete("/api/sites/categories/{name}")
def api_sites_del_cat(name: str):
    if not sites.delete_category(name):
        raise HTTPException(404, "not found")
    return {"ok": True}


@app.put("/api/sites/categories/{name}")
async def api_sites_rename_cat(name: str, request: Request):
    data = await request.json()
    new = (data.get("new") or "").strip()
    if not sites.rename_category(name, new):
        raise HTTPException(400, "rename failed")
    return {"ok": True}


@app.post("/api/sites/categories/{name}/sites")
async def api_sites_add_site(name: str, request: Request):
    data = await request.json()
    host = (data.get("host") or "").strip()
    site_name = (data.get("name") or "").strip()
    if not host:
        raise HTTPException(400, "host required")
    if not sites.add_site(name, host, site_name):
        raise HTTPException(400, "add failed")
    return {"ok": True}


@app.delete("/api/sites/categories/{name}/sites/{idx}")
def api_sites_del_site(name: str, idx: int):
    if not sites.delete_site(name, idx):
        raise HTTPException(404, "not found")
    return {"ok": True}


@app.put("/api/sites/categories/{name}/sites/{idx}")
async def api_sites_upd_site(name: str, idx: int, request: Request):
    data = await request.json()
    host = (data.get("host") or "").strip()
    site_name = (data.get("name") or "").strip()
    if not host:
        raise HTTPException(400, "host required")
    if not sites.update_site(name, idx, host, site_name):
        raise HTTPException(404, "not found")
    return {"ok": True}


@app.post("/api/sites/categories/{name}/bulk")
async def api_sites_bulk(name: str, request: Request):
    data = await request.json()
    text = data.get("text") or ""
    count = sites.bulk_import(name, text)
    return {"added": count}


@app.post("/api/sites/reset")
def api_sites_reset():
    if not sites.reset_to_default():
        raise HTTPException(404, "no default backup")
    return {"ok": True}


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


@app.post("/api/reports/save-json")
async def api_reports_save_json(request: Request):
    data = await request.json()
    prefix = (data.get("prefix") or "report").strip()
    payload = data.get("data")
    if payload is None:
        raise HTTPException(400, "data required")
    name = reports.save_json(prefix, payload)
    return {"name": name}


# ── REST: suggestions ────────────────────────────────────────────────────────────

@app.post("/api/suggestions")
async def api_suggestions(request: Request):
    data = await request.json()
    return {"suggestions": suggestions.analyze(data)}


# ── REST: version / updates ──────────────────────────────────────────────────────

def _semver_tuple(v: str) -> tuple:
    parts = v.lstrip("v").split(".")
    out = []
    for p in parts:
        try: out.append(int(p))
        except ValueError: out.append(0)
    while len(out) < 3:
        out.append(0)
    return tuple(out[:3])


@app.get("/api/version")
def api_version():
    try:
        import requests as _req
        r = _req.get(GITHUB_LATEST_API, timeout=(3, 5),
                     headers={"Accept": "application/vnd.github+json"})
        if r.status_code == 200:
            data = r.json()
            latest = data.get("tag_name", "").strip()
            update_available = (
                latest
                and _semver_tuple(latest) > _semver_tuple(APP_VERSION)
            )
            return {
                "current": APP_VERSION,
                "latest": latest,
                "update_available": update_available,
                "release_url": data.get("html_url") or GITHUB_RELEASES_URL,
                "release_notes": (data.get("body") or "")[:600],
            }
    except Exception:
        pass
    return {
        "current": APP_VERSION,
        "latest": None,
        "update_available": False,
        "release_url": GITHUB_RELEASES_URL,
    }


# ── REST: open reports folder in OS file manager ─────────────────────────────────

@app.post("/api/reports/open-folder")
def api_open_reports_folder():
    path = str(reports.REPORTS_DIR.resolve())
    try:
        if IS_WINDOWS:
            os.startfile(path)  # type: ignore[attr-defined]
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
        return {"ok": True, "path": path}
    except Exception as e:
        raise HTTPException(500, f"failed: {e}")


# ── REST: live dashboard ─────────────────────────────────────────────────────────

@app.get("/api/live/services")
def api_live_services():
    return {"services": live_dashboard.load_services()}


@app.put("/api/live/services")
async def api_live_set_services(request: Request):
    data = await request.json()
    svcs = data.get("services")
    if not isinstance(svcs, list):
        raise HTTPException(400, "services must be list")
    live_dashboard.save_services(svcs)
    return {"ok": True}


@app.get("/api/live/check")
def api_live_check():
    return {"results": live_dashboard.check_all()}


# ── SSE: raw streams ─────────────────────────────────────────────────────────────

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


# ── SSE: batch monitor ───────────────────────────────────────────────────────────

@app.get("/api/stream/batch")
async def stream_batch(
    categories: Optional[str] = Query(None),
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
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    url = f"http://{args.host}:{args.port}"
    print(f"\n  netmon-web → {url}\n")
    if not args.no_browser:
        _open_browser_delayed(url)
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
