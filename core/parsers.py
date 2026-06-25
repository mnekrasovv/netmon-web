"""Parsers: raw command output -> structured dicts."""

from __future__ import annotations

import re
import statistics
from typing import Optional

from .runner import IS_WINDOWS


def parse_ping(out: str, host: str, count: int) -> dict:
    """Parse ping output into structured stats including per-packet times."""
    times: list = []

    if IS_WINDOWS:
        for line in out.splitlines():
            m = re.search(r"time[=<](\d+)\s*ms", line, re.IGNORECASE)
            if m:
                times.append(float(m.group(1)))
                continue
            m = re.search(r"\b(\d+)\s*мс", line)
            if m and ("byte" in line.lower() or "ответ" in line.lower() or "TTL" in line):
                times.append(float(m.group(1)))
    else:
        for line in out.splitlines():
            m = re.search(r"time=([\d.]+)\s*ms", line)
            if m:
                times.append(float(m.group(1)))

    loss = 100.0
    if IS_WINDOWS:
        loss_m = re.search(r"\((\d+)%[^)]*\)", out)
        if loss_m:
            loss = float(loss_m.group(1))
    else:
        loss_m = re.search(r"(\d+)%\s+packet loss", out)
        if loss_m:
            loss = float(loss_m.group(1))

    sent = count
    recv = len(times) if times else int(round(count * (1 - loss / 100)))

    mn = avg = mx = jitter = None
    if times:
        mn = min(times)
        mx = max(times)
        avg = sum(times) / len(times)
        if len(times) > 1:
            diffs = [abs(times[i] - times[i - 1]) for i in range(1, len(times))]
            jitter = sum(diffs) / len(diffs)

    return {
        "host": host,
        "sent": sent,
        "recv": recv,
        "loss": round(loss, 1),
        "min": round(mn, 2) if mn is not None else None,
        "avg": round(avg, 2) if avg is not None else None,
        "max": round(mx, 2) if mx is not None else None,
        "jitter": round(jitter, 2) if jitter is not None else None,
        "times": [round(t, 2) for t in times],
        "ok": recv > 0,
    }


def parse_traceroute(out: str) -> list:
    """Parse traceroute / tracert output into list of hops."""
    hops = []
    in_table = False

    for line in out.splitlines():
        m = re.match(r"^\s*(\d+)\s+(.+?)$", line)
        if not m:
            continue
        in_table = True
        hop_n = int(m.group(1))
        rest = m.group(2)

        ip_m = re.search(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b", rest)
        ip = ip_m.group(1) if ip_m else None

        rtts: list = []
        for tm in re.finditer(r"<?\s*([\d.]+)\s*(?:ms|мс)", rest):
            try:
                v = float(tm.group(1))
                rtts.append(v)
            except ValueError:
                pass
        for _ in re.finditer(r"<\s*1\s*(?:ms|мс)", rest):
            rtts.append(0.5)

        timeout = "*" in rest and not ip and not rtts

        hops.append({
            "hop": hop_n,
            "ip": ip,
            "rtts": [round(x, 2) for x in rtts],
            "avg_rtt": round(sum(rtts) / len(rtts), 2) if rtts else None,
            "timeout": timeout,
        })

    return hops


def parse_interfaces_linux(out: str) -> list:
    """Parse `ip addr show` output into structured interface list."""
    interfaces = []
    current: Optional[dict] = None

    for line in out.splitlines():
        m = re.match(r"^(\d+):\s+([^:@]+)(?:@[^:]+)?:\s+<([^>]+)>(.*)$", line)
        if m:
            if current:
                interfaces.append(current)
            flags = m.group(3).split(",")
            current = {
                "index": int(m.group(1)),
                "name": m.group(2).strip(),
                "flags": flags,
                "up": "UP" in flags,
                "loopback": "LOOPBACK" in flags,
                "addresses": [],
                "mac": None,
                "mtu": None,
            }
            mtu_m = re.search(r"mtu\s+(\d+)", line)
            if mtu_m:
                current["mtu"] = int(mtu_m.group(1))
            continue

        if current is None:
            continue

        mac_m = re.search(r"link/(?:ether|loopback)\s+([0-9a-fA-F:]+)", line)
        if mac_m:
            current["mac"] = mac_m.group(1)
            continue

        ip_m = re.search(r"\s+inet\s+([\d.]+)/(\d+)", line)
        if ip_m:
            current["addresses"].append({
                "family": "v4",
                "addr": ip_m.group(1),
                "prefix": int(ip_m.group(2)),
            })
            continue

        ip6_m = re.search(r"\s+inet6\s+([0-9a-fA-F:]+)/(\d+)", line)
        if ip6_m:
            current["addresses"].append({
                "family": "v6",
                "addr": ip6_m.group(1),
                "prefix": int(ip6_m.group(2)),
            })

    if current:
        interfaces.append(current)
    return interfaces


def parse_interfaces_windows(out: str) -> list:
    """Parse `ipconfig /all` output into structured interface list."""
    interfaces = []
    current: Optional[dict] = None
    section_started = False

    for line in out.splitlines():
        if not line.strip():
            continue
        if re.match(r"^[A-Za-zА-Яа-я].+:\s*$", line) and " : " not in line:
            if current:
                interfaces.append(current)
            section_started = True
            name_m = re.match(r"^(?:[A-Za-zА-Яа-я ]+adapter\s+|.+ адаптер\s+)?(.+?):\s*$", line)
            current = {
                "name": name_m.group(1).strip() if name_m else line.strip().rstrip(":"),
                "addresses": [],
                "mac": None,
                "mtu": None,
                "flags": [],
                "up": True,
                "loopback": False,
                "dns": [],
                "dhcp": None,
            }
            continue

        if current is None:
            continue

        lower = line.lower()
        if "physical address" in lower or "физический адрес" in lower:
            mac_m = re.search(r":\s*([0-9A-Fa-f-]+)\s*$", line)
            if mac_m:
                current["mac"] = mac_m.group(1).replace("-", ":").lower()
        elif ("ipv4 address" in lower or "ip address" in lower or "ipv4-адрес" in lower or "ip-адрес" in lower):
            ip_m = re.search(r":\s*([\d.]+)", line)
            if ip_m:
                current["addresses"].append({"family": "v4", "addr": ip_m.group(1), "prefix": 24})
        elif "ipv6 address" in lower or "link-local ipv6" in lower or "ipv6-адрес" in lower:
            ip_m = re.search(r":\s*([0-9a-fA-F:]+)", line)
            if ip_m:
                current["addresses"].append({"family": "v6", "addr": ip_m.group(1), "prefix": 64})
        elif "media state" in lower or "состояние среды" in lower:
            current["up"] = "disconnect" not in lower
        elif "dns servers" in lower or "dns-серверы" in lower:
            dns_m = re.search(r":\s*([\d.]+)", line)
            if dns_m:
                current["dns"].append(dns_m.group(1))

    if current:
        interfaces.append(current)
    return [i for i in interfaces if i.get("addresses") or i.get("mac")]


def parse_interfaces(out: str) -> list:
    if IS_WINDOWS:
        return parse_interfaces_windows(out)
    return parse_interfaces_linux(out)


def parse_connections_ss(out: str) -> list:
    """Parse `ss -tuln` or `ss -tun` output."""
    rows = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 5 or parts[0] == "Netid":
            continue
        proto = parts[0]
        state = parts[1] if len(parts) > 4 else "—"
        local = parts[-2]
        remote = parts[-1]
        rows.append({
            "proto": proto, "state": state,
            "local": local, "remote": remote,
        })
    return rows


def parse_connections_netstat(out: str) -> list:
    """Parse `netstat -an` output (Windows + Linux fallback)."""
    rows = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        proto = parts[0].upper()
        if proto not in ("TCP", "UDP"):
            continue
        local = parts[1]
        remote = parts[2] if len(parts) > 2 else "—"
        state = parts[3] if len(parts) > 3 and parts[3] != remote else "—"
        rows.append({
            "proto": proto, "state": state,
            "local": local, "remote": remote,
        })
    return rows
