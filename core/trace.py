"""Traceroute + MTR (pure Python fallback)."""

from __future__ import annotations

import re
from typing import Iterator

from .ping import ping_stats
from .runner import IS_WINDOWS, has, run_cmd, stream_cmd


def trace_stream(host: str) -> Iterator[str]:
    if IS_WINDOWS:
        yield from stream_cmd(["tracert", "-d", host], timeout=180)
    elif has("traceroute"):
        yield from stream_cmd(
            ["traceroute", "-n", "-w", "3", "-m", "30", host], timeout=180
        )
    elif has("tracepath"):
        yield from stream_cmd(["tracepath", "-n", host], timeout=180)
    else:
        yield "[!] traceroute и tracepath не найдены. Установите: sudo apt install traceroute"


def _get_trace_output(host: str) -> str:
    if IS_WINDOWS:
        return run_cmd(["tracert", "-d", host], timeout=120)
    if has("traceroute"):
        return run_cmd(["traceroute", "-n", "-w", "2", "-m", "30", host], timeout=120)
    if has("tracepath"):
        return run_cmd(["tracepath", "-n", host], timeout=120)
    return ""


def mtr_stream(host: str, cycles: int = 10) -> Iterator[str]:
    """MTR: native if available (Linux), else pure-Python implementation."""
    if not IS_WINDOWS and has("mtr"):
        yield from stream_cmd(
            ["mtr", "--report", f"--report-cycles={cycles}", "--no-dns", host],
            timeout=cycles * 10 + 30,
        )
        return

    yield "Получение маршрута..."
    trace_out = _get_trace_output(host)
    if not trace_out:
        yield "[!] traceroute/tracepath не найдены"
        return

    hops = []
    for line in trace_out.splitlines():
        if not re.match(r"^\s*\d+", line):
            continue
        ip_m = re.search(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b", line)
        if ip_m:
            hops.append(ip_m.group(1))
        elif "*" in line:
            hops.append("*")

    if not hops:
        yield "[!] Маршрут не получен"
        return

    yield f"  {'Hop':<4}  {'IP':<17}  {'Loss%':>7}  {'Sent':>6}  {'Recv':>6}  {'Avg ms':>8}"
    yield "  " + "─" * 58

    seen: set = set()
    hop_n = 1
    for ip in hops:
        if ip == "*":
            yield f"  {hop_n:<4}  {'* * *':<17}  {'100.0%':>7}"
            hop_n += 1
            continue
        if ip in seen:
            continue
        seen.add(ip)

        stats = ping_stats(ip, count=cycles, fast=True)
        loss = stats["loss"]
        avg = f"{stats['avg']:.1f}" if stats["avg"] is not None else "-"
        recv = stats["recv"]
        sent = stats["sent"]

        yield f"  {hop_n:<4}  {ip:<17}  {loss:>6.1f}%  {sent:>6}  {recv:>6}  {avg:>8}"
        hop_n += 1
