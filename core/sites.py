"""Sites CRUD: full editing of configs/sites.json (categories + sites)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

SITES_FILE = Path(__file__).parent.parent / "configs" / "sites.json"
DEFAULT_BACKUP = SITES_FILE.parent / "sites.default.json"


def _load_raw() -> dict:
    if not SITES_FILE.exists():
        return {"categories": {}}
    return json.loads(SITES_FILE.read_text(encoding="utf-8"))


def _save(data: dict):
    SITES_FILE.parent.mkdir(parents=True, exist_ok=True)
    SITES_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    if not DEFAULT_BACKUP.exists() and SITES_FILE.exists():
        shutil.copy(SITES_FILE, DEFAULT_BACKUP)


def get_all() -> dict:
    """Returns {categories: {name: [sites]}}."""
    return _load_raw()


def get_summary() -> dict:
    """For Monitor tab: {categories: [{name, count}], total}."""
    data = _load_raw()
    cats = []
    total = 0
    for name, sites in data.get("categories", {}).items():
        cats.append({"name": name, "count": len(sites)})
        total += len(sites)
    return {"categories": cats, "total": total}


def add_category(name: str) -> bool:
    name = (name or "").strip()
    if not name:
        return False
    data = _load_raw()
    cats = data.setdefault("categories", {})
    if name in cats:
        return False
    cats[name] = []
    _save(data)
    return True


def delete_category(name: str) -> bool:
    data = _load_raw()
    if name not in data.get("categories", {}):
        return False
    del data["categories"][name]
    _save(data)
    return True


def rename_category(old: str, new: str) -> bool:
    new = (new or "").strip()
    if not new:
        return False
    data = _load_raw()
    cats = data.get("categories", {})
    if old not in cats or new in cats:
        return False
    cats[new] = cats.pop(old)
    _save(data)
    return True


def add_site(category: str, host: str, name: str = "") -> bool:
    host = (host or "").strip()
    if not host:
        return False
    data = _load_raw()
    cats = data.setdefault("categories", {})
    cats.setdefault(category, []).append({
        "host": host,
        "name": name.strip() or host,
    })
    _save(data)
    return True


def delete_site(category: str, idx: int) -> bool:
    data = _load_raw()
    sites = data.get("categories", {}).get(category)
    if sites is None or not (0 <= idx < len(sites)):
        return False
    del sites[idx]
    _save(data)
    return True


def update_site(category: str, idx: int, host: str, name: str) -> bool:
    data = _load_raw()
    sites = data.get("categories", {}).get(category)
    if sites is None or not (0 <= idx < len(sites)):
        return False
    sites[idx]["host"] = host.strip()
    sites[idx]["name"] = name.strip() or host.strip()
    _save(data)
    return True


def bulk_import(category: str, text: str) -> int:
    """Parse text (one host per line, optional ' name' after host). Returns count added."""
    data = _load_raw()
    sites = data.setdefault("categories", {}).setdefault(category, [])
    count = 0
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        host = parts[0]
        name = parts[1] if len(parts) > 1 else host
        sites.append({"host": host, "name": name})
        count += 1
    _save(data)
    return count


def reset_to_default() -> bool:
    if not DEFAULT_BACKUP.exists():
        return False
    shutil.copy(DEFAULT_BACKUP, SITES_FILE)
    return True
