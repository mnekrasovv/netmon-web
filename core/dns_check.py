"""DNS resolution + matrix + DNS server pings."""

from __future__ import annotations

import re
import socket
from typing import Iterator

from .ping import ping_stats
from .runner import has, run_cmd

DNS_SERVERS = [
    ("8.8.8.8",   "Google"),
    ("1.1.1.1",   "Cloudflare"),
    ("77.88.8.8", "Yandex"),
    ("9.9.9.9",   "Quad9"),
]
DNS_DOMAINS = ["google.com", "ya.ru", "vk.com", "youtube.com", "github.com"]


def resolve_ip(domain: str, server: str = "") -> str:
    try:
        if not server:
            return socket.gethostbyname(domain)
        if has("nslookup"):
            out = run_cmd(["nslookup", domain, server], timeout=10)
            ips = re.findall(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b", out)
            filtered = [ip for ip in ips if ip != server]
            if filtered:
                return filtered[-1]
        if has("dig"):
            out = run_cmd(["dig", f"@{server}", domain, "+short"], timeout=10)
            for line in out.splitlines():
                if re.match(r"^\d+\.\d+\.\d+\.\d+$", line.strip()):
                    return line.strip()
    except Exception:
        pass
    return "FAIL"


def dns_matrix() -> dict:
    """Returns matrix data: {domains, servers, results: {domain: {server_name: ip}}}."""
    results = {}
    for domain in DNS_DOMAINS:
        row = {"Системный": resolve_ip(domain)}
        for ip, name in DNS_SERVERS:
            row[name] = resolve_ip(domain, ip)
        results[domain] = row
    return {
        "domains": DNS_DOMAINS,
        "servers": ["Системный"] + [name for _, name in DNS_SERVERS],
        "results": results,
    }


def dns_server_pings() -> list:
    out = []
    for ip, name in DNS_SERVERS:
        s = ping_stats(ip, count=3, fast=True)
        out.append({"ip": ip, "name": name, "avg": s["avg"], "loss": s["loss"]})
    return out


def dns_stream() -> Iterator[str]:
    yield "── DNS ДИАГНОСТИКА ──"
    yield ""
    yield "Матрица DNS-резолюции:"
    col_w = 16
    header = f"  {'Домен':<22}  {'Системный':<{col_w}}"
    for _, name in DNS_SERVERS:
        header += f"  {name:<{col_w}}"
    yield header
    yield "  " + "─" * (22 + col_w * (len(DNS_SERVERS) + 1) + 10)

    for domain in DNS_DOMAINS:
        row = f"  {domain:<22}"
        row += f"  {resolve_ip(domain):<{col_w}}"
        for ip, _ in DNS_SERVERS:
            row += f"  {resolve_ip(domain, ip):<{col_w}}"
        yield row

    yield ""
    yield "Пинг до DNS серверов:"
    for ip, name in DNS_SERVERS:
        stats = ping_stats(ip, count=3, fast=True)
        if stats["avg"] is not None:
            yield f"  {ip:<12} ({name:<10}): avg {stats['avg']:.1f}ms  loss={stats['loss']:.0f}%"
        else:
            yield f"  {ip:<12} ({name:<10}): недостижим"
