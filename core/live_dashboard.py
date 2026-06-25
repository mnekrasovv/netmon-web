"""Live dashboard data: parallel checks of curated 'flagship' services."""

from __future__ import annotations

import concurrent.futures
import json
from pathlib import Path

from .ping import ping_stats
from .tcp_check import check_port

LIVE_FILE = Path(__file__).parent.parent / "configs" / "live.json"

DEFAULT_SERVICES = [
    {"name": "Google",        "host": "google.com",        "port": 443, "kind": "web"},
    {"name": "YouTube",       "host": "youtube.com",       "port": 443, "kind": "web"},
    {"name": "Cloudflare DNS","host": "1.1.1.1",           "port": 53,  "kind": "dns"},
    {"name": "Google DNS",    "host": "8.8.8.8",           "port": 53,  "kind": "dns"},
    {"name": "GitHub",        "host": "github.com",        "port": 443, "kind": "web"},
    {"name": "Yandex",        "host": "ya.ru",             "port": 443, "kind": "web"},
    {"name": "VK",            "host": "vk.com",            "port": 443, "kind": "web"},
    {"name": "Telegram",      "host": "telegram.org",      "port": 443, "kind": "web"},
    {"name": "Discord",       "host": "discord.com",       "port": 443, "kind": "web"},
    {"name": "Steam",         "host": "store.steampowered.com", "port": 443, "kind": "web"},
]


def load_services() -> list:
    if not LIVE_FILE.exists():
        LIVE_FILE.parent.mkdir(parents=True, exist_ok=True)
        LIVE_FILE.write_text(json.dumps(DEFAULT_SERVICES, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        return json.loads(LIVE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return DEFAULT_SERVICES


def save_services(services: list):
    LIVE_FILE.parent.mkdir(parents=True, exist_ok=True)
    LIVE_FILE.write_text(json.dumps(services, ensure_ascii=False, indent=2), encoding="utf-8")


def _check_one(svc: dict) -> dict:
    host = svc["host"]
    port = svc.get("port", 443)
    p = ping_stats(host, count=2, fast=True)
    tcp = check_port(host, port, timeout=2.5)

    avg = p.get("avg")
    loss = p.get("loss", 100)

    if not tcp["open"] and not p.get("ok"):
        status = "FAIL"
    elif loss >= 50 or (avg and avg > 300) or not tcp["open"]:
        status = "WARN"
    elif loss >= 10 or (avg and avg > 150):
        status = "SLOW"
    else:
        status = "OK"

    return {
        "name":     svc["name"],
        "host":     host,
        "port":     port,
        "kind":     svc.get("kind", "web"),
        "status":   status,
        "ping_avg": avg,
        "ping_loss": loss,
        "tcp_open": tcp["open"],
        "tcp_ms":   tcp.get("time_ms"),
    }


def check_all(services: list = None) -> list:
    services = services or load_services()
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        return list(ex.map(_check_one, services))
