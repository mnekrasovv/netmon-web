"""Ping operations: streamed lines + structured stats."""

from __future__ import annotations

import re
from typing import Iterator

from .runner import IS_WINDOWS, run_cmd, stream_cmd


def _ping_cmd(host: str, count: int, fast: bool = False) -> list:
    if fast:
        count = min(count, 5)
        w_ms, w_lin, interval = "800", "1", "0.3"
    else:
        w_ms, w_lin, interval = "1500", "2", "0.5"

    if IS_WINDOWS:
        return ["ping", "-n", str(count), "-w", w_ms, host]
    return ["ping", "-c", str(count), "-W", w_lin, "-i", interval, host]


def _ping_timeout(count: int, fast: bool = False) -> int:
    per_packet = 1 if fast else 3
    return count * per_packet + 10


def ping_stream(host: str, count: int = 10) -> Iterator[str]:
    """Yield ping output lines in real-time."""
    cmd = _ping_cmd(host, count)
    yield from stream_cmd(cmd, timeout=_ping_timeout(count))


def ping_stats(host: str, count: int = 10, fast: bool = False) -> dict:
    """Run ping and parse aggregated stats."""
    cmd = _ping_cmd(host, count, fast=fast)
    out = run_cmd(cmd, timeout=_ping_timeout(count, fast=fast))

    loss = 100.0
    mn = avg = mx = None

    if IS_WINDOWS:
        loss_m = re.search(r"\((\d+)%[^)]*\)", out)
        if loss_m:
            loss = float(loss_m.group(1))
        avg_m = re.search(r"Average\s*=\s*(\d+)\s*ms", out, re.IGNORECASE)
        min_m = re.search(r"Minimum\s*=\s*(\d+)\s*ms", out, re.IGNORECASE)
        max_m = re.search(r"Maximum\s*=\s*(\d+)\s*ms", out, re.IGNORECASE)
        if avg_m:
            avg = float(avg_m.group(1))
            mn = float(min_m.group(1)) if min_m else None
            mx = float(max_m.group(1)) if max_m else None
        else:
            nums = re.findall(r"(\d+)\s*мс", out)
            if len(nums) >= 3:
                mn, mx, avg = float(nums[0]), float(nums[1]), float(nums[2])
    else:
        loss_m = re.search(r"(\d+)%\s+packet loss", out)
        if loss_m:
            loss = float(loss_m.group(1))
        rtt_m = re.search(r"(?:rtt|round-trip)\s+\S+\s*=\s*([\d.]+)/([\d.]+)/([\d.]+)", out)
        if rtt_m:
            mn, avg, mx = float(rtt_m.group(1)), float(rtt_m.group(2)), float(rtt_m.group(3))

    return {
        "host": host,
        "loss": loss,
        "min": mn,
        "avg": avg,
        "max": mx,
        "ok": loss < 100.0 and avg is not None,
        "sent": count,
        "recv": int(round(count * (1 - loss / 100))) if loss < 100 else 0,
    }


def get_gateway() -> str:
    try:
        if IS_WINDOWS:
            out = run_cmd(["route", "print", "0.0.0.0"], timeout=10)
            for line in out.splitlines():
                m = re.search(r"0\.0\.0\.0\s+0\.0\.0\.0\s+(\d+\.\d+\.\d+\.\d+)", line)
                if m:
                    return m.group(1)
        else:
            from .runner import has
            if has("ip"):
                out = run_cmd(["ip", "route"], timeout=10)
                for line in out.splitlines():
                    m = re.match(r"default\s+via\s+(\S+)", line)
                    if m:
                        return m.group(1)
    except Exception:
        pass
    return ""
