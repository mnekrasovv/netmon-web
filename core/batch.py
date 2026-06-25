"""Batch site monitoring: parallel ping + HTTP check (replaces monitor_windows.py)."""

from __future__ import annotations

import concurrent.futures
import json
import re
import threading
from pathlib import Path
from typing import Iterator

from .http_check import http_check
from .ping import ping_stats

SITES_FILE = Path(__file__).parent.parent / "configs" / "sites.json"


def load_sites() -> dict:
    if not SITES_FILE.exists():
        return {"categories": {}}
    return json.loads(SITES_FILE.read_text(encoding="utf-8"))


def calc_status(r: dict) -> str:
    loss = r.get("loss", 100)
    avg = r.get("avg")
    htime = r.get("http_time_ms")
    http_ok = r.get("http_ok")

    if loss >= 50:
        return "FAIL"
    if not r.get("ping_ok") and http_ok is False:
        return "FAIL"
    if loss >= 10 or (avg and avg > 300) or (htime and htime > 3000) or http_ok is False:
        return "WARN"
    if loss >= 2 or (avg and avg > 150) or (htime and htime > 1500):
        return "SLOW"
    return "OK"


def _check_site(args: tuple) -> dict:
    site, ping_count, http_timeout, no_http = args
    host = site["host"]
    is_ip = bool(re.match(r"^\d+\.\d+\.\d+\.\d+$", host))
    url = site.get("url") or ("" if is_ip else f"https://{host}")

    result = {
        "name": site["name"],
        "category": site.get("category", "other"),
        "host": host,
        "url": url,
    }

    pstat = ping_stats(host, count=ping_count)
    result.update({
        "loss": pstat["loss"],
        "avg": pstat["avg"],
        "min": pstat["min"],
        "max": pstat["max"],
        "ping_ok": pstat["ok"],
    })

    if not no_http and not is_ip and url:
        h = http_check(url, timeout=http_timeout)
        result["http_ok"] = h["ok"]
        result["http_status"] = h.get("status")
        result["http_time_ms"] = h.get("time_ms")
        if not h["ok"]:
            result["http_error"] = h.get("error", "ERR")
    else:
        result["http_ok"] = None

    result["status"] = calc_status(result)
    return result


def batch_check_stream(
    categories: list = None,
    ping_count: int = 10,
    workers: int = 20,
    no_http: bool = False,
    http_timeout: int = 10,
    custom_sites: list = None,
) -> Iterator[dict]:
    """Yields events: {type: 'meta'|'result'|'progress'|'summary'|'done', payload: ...}"""
    config = load_sites()
    all_sites = []
    for category, sites in config.get("categories", {}).items():
        if categories and category not in categories:
            continue
        for site in sites:
            site = dict(site)
            site["category"] = category
            all_sites.append(site)

    if custom_sites:
        for s in custom_sites:
            s = dict(s)
            s.setdefault("category", "custom")
            all_sites.append(s)

    total = len(all_sites)
    yield {"type": "meta", "payload": {"total": total, "ping_count": ping_count, "workers": workers}}

    if total == 0:
        yield {"type": "done"}
        return

    work = [(s, ping_count, http_timeout, no_http) for s in all_sites]
    done_count = [0]
    lock = threading.Lock()
    results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_check_site, w): w for w in work}
        for fut in concurrent.futures.as_completed(futs):
            try:
                r = fut.result()
                results.append(r)
                with lock:
                    done_count[0] += 1
                    n = done_count[0]
                yield {"type": "result", "payload": r}
                yield {"type": "progress", "payload": {"done": n, "total": total}}
            except Exception as e:
                yield {"type": "error", "payload": str(e)[:200]}

    ok = sum(1 for r in results if r["status"] == "OK")
    slow = sum(1 for r in results if r["status"] == "SLOW")
    warn = sum(1 for r in results if r["status"] == "WARN")
    fail = sum(1 for r in results if r["status"] == "FAIL")
    avg_loss = sum(r.get("loss") or 0 for r in results) / max(len(results), 1)

    yield {
        "type": "summary",
        "payload": {
            "total": total,
            "ok": ok, "slow": slow, "warn": warn, "fail": fail,
            "avg_loss": round(avg_loss, 2),
            "results": results,
        },
    }
    yield {"type": "done"}
