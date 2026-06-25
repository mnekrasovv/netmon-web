"""HTTP availability check + external IP."""

from __future__ import annotations

import json
import time
from typing import Iterator

try:
    import requests
    import urllib3
    urllib3.disable_warnings()
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    import urllib.request  # type: ignore


def http_check(url: str, timeout: int = 10) -> dict:
    if not url.startswith("http"):
        url = f"https://{url}"

    if REQUESTS_AVAILABLE:
        try:
            t0 = time.time()
            r = requests.get(
                url, timeout=(5, timeout), allow_redirects=True, verify=False,
                stream=True,
                headers={"User-Agent": "Mozilla/5.0 (netmon-web/1.0)"},
            )
            ms = (time.time() - t0) * 1000
            r.close()
            return {
                "url": url,
                "ok": r.status_code < 500,
                "status": r.status_code,
                "time_ms": round(ms, 0),
            }
        except requests.exceptions.Timeout:
            return {"url": url, "ok": False, "error": "timeout", "time_ms": timeout * 1000}
        except Exception as e:
            return {"url": url, "ok": False, "error": str(e)[:60], "time_ms": None}

    try:
        req = urllib.request.Request(  # type: ignore
            url, headers={"User-Agent": "Mozilla/5.0 (netmon-web/1.0)"}
        )
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # type: ignore
            ms = (time.time() - t0) * 1000
            return {
                "url": url,
                "ok": True,
                "status": resp.status,
                "time_ms": round(ms, 0),
            }
    except Exception as e:
        return {"url": url, "ok": False, "error": str(e)[:60], "time_ms": None}


def http_check_stream(url: str, timeout: int = 10) -> Iterator[str]:
    if not url.startswith("http"):
        url = f"https://{url}"
    yield f"GET {url}"
    r = http_check(url, timeout)
    if r["ok"]:
        yield f"  HTTP {r['status']}  time={r['time_ms']:.0f}ms"
    else:
        err = r.get("error", "ERR")
        yield f"  ERR: {err}"


def external_ip() -> dict:
    """Get external IP via multiple services + geo info."""
    services = [
        "https://ifconfig.me",
        "https://api.ipify.org",
        "https://checkip.amazonaws.com",
    ]
    ips = {}
    for svc in services:
        try:
            if REQUESTS_AVAILABLE:
                r = requests.get(svc, timeout=(5, 5))
                ips[svc] = r.text.strip()
            else:
                with urllib.request.urlopen(svc, timeout=8) as resp:  # type: ignore
                    ips[svc] = resp.read().decode().strip()
        except Exception:
            ips[svc] = None

    geo = {}
    try:
        if REQUESTS_AVAILABLE:
            geo = requests.get("https://ipinfo.io/json", timeout=(5, 8)).json()
        else:
            with urllib.request.urlopen("https://ipinfo.io/json", timeout=10) as resp:  # type: ignore
                geo = json.loads(resp.read().decode())
    except Exception:
        geo = {}

    return {"services": ips, "geo": geo}


def external_ip_stream() -> Iterator[str]:
    data = external_ip()
    yield "── ВНЕШНИЙ IP ──"
    yield ""
    for svc, ip in data["services"].items():
        yield f"  {svc:<45}: {ip or 'недоступен'}"
    yield ""
    yield "Гео-информация (ipinfo.io):"
    geo = data["geo"]
    if not geo:
        yield "  ipinfo.io недоступен"
        return
    for key, label in [
        ("ip", "IP"),
        ("hostname", "Hostname"),
        ("city", "Город"),
        ("region", "Регион"),
        ("country", "Страна"),
        ("org", "Провайдер"),
        ("timezone", "Timezone"),
    ]:
        if key in geo:
            yield f"  {label:<10}: {geo[key]}"
