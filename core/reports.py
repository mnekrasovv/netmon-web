"""Report storage: list, save, read, delete."""

from __future__ import annotations

import datetime
import json
from pathlib import Path

REPORTS_DIR = Path(__file__).parent.parent / "reports"
REPORTS_DIR.mkdir(exist_ok=True, parents=True)


def _ts() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def save_text(prefix: str, lines: list) -> str:
    name = f"{prefix}_{_ts()}.txt"
    (REPORTS_DIR / name).write_text("\n".join(lines), encoding="utf-8")
    return name


def save_json(prefix: str, data: dict) -> str:
    name = f"{prefix}_{_ts()}.json"
    (REPORTS_DIR / name).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return name


def save_html_batch(summary: dict) -> str:
    """Save HTML report for batch monitoring run."""
    name = f"batch_{_ts()}.html"
    results = summary.get("results", [])
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    avg_loss = summary.get("avg_loss", 0)
    loss_color = "#e74c3c" if avg_loss > 5 else ("#f39c12" if avg_loss > 1 else "#2ecc71")
    order = {"FAIL": 0, "WARN": 1, "SLOW": 2, "OK": 3}
    sorted_r = sorted(results, key=lambda x: (order.get(x.get("status", "OK"), 4), -(x.get("loss") or 0)))

    colors = {"OK": "#2ecc71", "SLOW": "#f39c12", "WARN": "#e67e22", "FAIL": "#e74c3c"}
    rows = []
    for r in sorted_r:
        sc = colors.get(r.get("status", "OK"), "#aaa")
        loss = r.get("loss", 100)
        lc = "#2ecc71" if loss == 0 else ("#f39c12" if loss < 10 else "#e74c3c")
        avg = r.get("avg")
        mx = r.get("max")
        htime = r.get("http_time_ms")
        hstatus = r.get("http_status", "")
        hok = r.get("http_ok")
        if hok is None:
            http_cell = "N/A"
        elif not hok:
            err = (r.get("http_error") or "ERR")[:30]
            http_cell = f'<span style="color:#e74c3c">ERR: {err}</span>'
        else:
            hc = "#2ecc71" if htime and htime < 500 else ("#f39c12" if htime and htime < 2000 else "#e74c3c")
            http_cell = f'<span style="color:{hc}">{htime:.0f}ms</span> ({hstatus})'
        rows.append(f"""
        <tr>
          <td>{r.get('name','')}</td>
          <td><code>{r.get('host','')}</code></td>
          <td style="color:#aaa;font-size:0.85em">{(r.get('category','')).replace('_',' ').title()}</td>
          <td><span style="color:{lc}">{loss:.1f}%</span></td>
          <td>{f"{avg:.1f}" if avg is not None else "&mdash;"}</td>
          <td>{f"{mx:.1f}" if mx is not None else "&mdash;"}</td>
          <td>{http_cell}</td>
          <td><span style="display:inline-block;padding:2px 10px;border-radius:12px;color:#fff;font-weight:700;font-size:0.82em;background:{sc}">{r.get('status','')}</span></td>
        </tr>""")

    html = f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="UTF-8"><title>netmon-web batch — {ts}</title>
<style>
body {{ font-family: 'Segoe UI', Arial, sans-serif; background:#12121e; color:#dde; margin:0; padding:24px; }}
h1 {{ color:#00d4ff; margin:0 0 4px; }}
.meta {{ color:#888; font-size:0.9em; margin-bottom:20px; }}
.stats {{ display:flex; gap:16px; flex-wrap:wrap; margin-bottom:24px; }}
.stat {{ background:#1c1c2e; padding:14px 22px; border-radius:10px; text-align:center; min-width:90px; }}
.stat .val {{ font-size:2em; font-weight:bold; line-height:1.1; }}
.stat .lbl {{ color:#888; font-size:0.8em; margin-top:4px; }}
table {{ width:100%; border-collapse:collapse; font-size:0.92em; }}
th {{ background:#1c1c2e; color:#00d4ff; padding:10px 12px; text-align:left; }}
td {{ padding:7px 12px; border-bottom:1px solid #22223a; vertical-align:middle; }}
tr:hover td {{ background:#1a1a30; }}
code {{ color:#78d8ff; font-size:0.88em; }}
</style></head><body>
<h1>netmon-web — batch report</h1>
<div class="meta">{ts}</div>
<div class="stats">
  <div class="stat"><div class="val" style="color:#2ecc71">{summary.get('ok',0)}</div><div class="lbl">OK</div></div>
  <div class="stat"><div class="val" style="color:#f39c12">{summary.get('slow',0)}</div><div class="lbl">SLOW</div></div>
  <div class="stat"><div class="val" style="color:#e67e22">{summary.get('warn',0)}</div><div class="lbl">WARN</div></div>
  <div class="stat"><div class="val" style="color:#e74c3c">{summary.get('fail',0)}</div><div class="lbl">FAIL</div></div>
  <div class="stat"><div class="val" style="color:{loss_color}">{avg_loss:.1f}%</div><div class="lbl">Avg Loss</div></div>
  <div class="stat"><div class="val" style="color:#aaa">{summary.get('total',0)}</div><div class="lbl">Всего</div></div>
</div>
<table>
<thead><tr><th>Сайт</th><th>Хост</th><th>Категория</th><th>Потери</th><th>Avg ms</th><th>Max ms</th><th>HTTP</th><th>Статус</th></tr></thead>
<tbody>{''.join(rows)}</tbody>
</table>
</body></html>"""
    (REPORTS_DIR / name).write_text(html, encoding="utf-8")
    return name


def list_reports() -> list:
    out = []
    for p in sorted(REPORTS_DIR.glob("*"), key=lambda x: x.stat().st_mtime, reverse=True):
        if p.name == ".gitkeep" or p.is_dir():
            continue
        out.append({
            "name": p.name,
            "size": p.stat().st_size,
            "mtime": datetime.datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds"),
            "type": p.suffix.lstrip("."),
        })
    return out


def read_report(name: str) -> str:
    p = REPORTS_DIR / name
    if not p.exists() or ".." in name or "/" in name or "\\" in name:
        raise FileNotFoundError(name)
    return p.read_text(encoding="utf-8")


def delete_report(name: str) -> bool:
    p = REPORTS_DIR / name
    if not p.exists() or ".." in name or "/" in name or "\\" in name:
        return False
    p.unlink()
    return True
