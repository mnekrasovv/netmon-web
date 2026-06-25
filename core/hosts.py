"""Hosts CRUD: hosts.conf in pipe format."""

from __future__ import annotations

from pathlib import Path

CONFIGS_DIR = Path(__file__).parent.parent / "configs"
HOSTS_FILE = CONFIGS_DIR / "hosts.conf"

_DEFAULT = """\
# Формат: хост|имя|категория
# Категории: dns, web, custom

# DNS серверы
8.8.8.8|Google DNS|dns
8.8.4.4|Google DNS 2|dns
1.1.1.1|Cloudflare DNS|dns
77.88.8.8|Yandex DNS|dns

# Основные сайты
google.com|Google|web
ya.ru|Яндекс|web
vk.com|ВКонтакте|web
youtube.com|YouTube|web
github.com|GitHub|web
"""


def _ensure():
    CONFIGS_DIR.mkdir(exist_ok=True, parents=True)
    if not HOSTS_FILE.exists():
        HOSTS_FILE.write_text(_DEFAULT, encoding="utf-8")


def list_hosts() -> list:
    _ensure()
    hosts = []
    for line in HOSTS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("|", 2)
        h = parts[0].strip()
        n = parts[1].strip() if len(parts) > 1 else h
        c = parts[2].strip() if len(parts) > 2 else "custom"
        if h:
            hosts.append({"host": h, "name": n, "cat": c})
    return hosts


def add_host(host: str, name: str = "", cat: str = "custom") -> dict:
    _ensure()
    name = name or host
    cat = cat or "custom"
    with open(HOSTS_FILE, "a", encoding="utf-8") as f:
        f.write(f"{host}|{name}|{cat}\n")
    return {"host": host, "name": name, "cat": cat}


def delete_host(idx: int) -> bool:
    _ensure()
    hosts = list_hosts()
    if not (0 <= idx < len(hosts)):
        return False
    target = hosts[idx]["host"]
    lines = HOSTS_FILE.read_text(encoding="utf-8").splitlines(keepends=True)
    new_lines = [l for l in lines if not l.strip().startswith(f"{target}|")]
    HOSTS_FILE.write_text("".join(new_lines), encoding="utf-8")
    return True


def update_host(idx: int, host: str, name: str, cat: str) -> bool:
    _ensure()
    hosts = list_hosts()
    if not (0 <= idx < len(hosts)):
        return False
    old_target = hosts[idx]["host"]
    lines = HOSTS_FILE.read_text(encoding="utf-8").splitlines()
    new_lines = []
    replaced = False
    for line in lines:
        stripped = line.strip()
        if not replaced and stripped and not stripped.startswith("#") and stripped.startswith(f"{old_target}|"):
            new_lines.append(f"{host}|{name or host}|{cat or 'custom'}")
            replaced = True
        else:
            new_lines.append(line)
    HOSTS_FILE.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return replaced
