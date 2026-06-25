"""Whois (raw socket) + nslookup wrappers."""

from __future__ import annotations

import re
import socket
from typing import Optional

from .runner import has, run_cmd

WHOIS_PORT = 43
WHOIS_TIMEOUT = 8


def _whois_query(server: str, query: str) -> str:
    try:
        with socket.create_connection((server, WHOIS_PORT), timeout=WHOIS_TIMEOUT) as s:
            s.sendall(f"{query}\r\n".encode())
            chunks = []
            while True:
                try:
                    s.settimeout(WHOIS_TIMEOUT)
                    data = s.recv(4096)
                except socket.timeout:
                    break
                if not data:
                    break
                chunks.append(data)
            return b"".join(chunks).decode("utf-8", errors="replace")
    except Exception as e:
        return f"[whois error: {e}]"


def whois(query: str) -> dict:
    """Query whois.iana.org -> referral -> final whois.
    Returns {raw, parsed: {...}}.
    """
    q = (query or "").strip()
    if not q:
        return {"raw": "", "parsed": {}}

    raw_iana = _whois_query("whois.iana.org", q)
    referral = None
    for line in raw_iana.splitlines():
        m = re.match(r"^\s*(?:refer|whois):\s*(\S+)", line, re.IGNORECASE)
        if m:
            referral = m.group(1).strip()
            break

    if referral:
        raw = _whois_query(referral, q)
        if "[whois error" in raw and not raw.strip().endswith("]"):
            raw = raw_iana
    else:
        raw = raw_iana

    parsed = _parse_whois(raw)
    return {"raw": raw, "parsed": parsed, "server": referral or "whois.iana.org"}


def _parse_whois(raw: str) -> dict:
    fields = {
        "registrar":     [r"^\s*Registrar:\s*(.+)$"],
        "organization":  [r"^\s*OrgName:\s*(.+)$", r"^\s*org-name:\s*(.+)$",
                          r"^\s*Registrant Organization:\s*(.+)$"],
        "country":       [r"^\s*Country:\s*(.+)$", r"^\s*country:\s*(.+)$"],
        "city":          [r"^\s*City:\s*(.+)$"],
        "asn":           [r"^\s*OriginAS:\s*(.+)$", r"^\s*origin:\s*(AS\d+)$"],
        "created":       [r"^\s*Creation Date:\s*(.+)$", r"^\s*created:\s*(.+)$",
                          r"^\s*RegDate:\s*(.+)$"],
        "expires":       [r"^\s*Registry Expiry Date:\s*(.+)$",
                          r"^\s*Registrar Registration Expiration Date:\s*(.+)$"],
        "updated":       [r"^\s*Updated Date:\s*(.+)$", r"^\s*last-modified:\s*(.+)$"],
        "name_servers":  [r"^\s*Name Server:\s*(\S+)", r"^\s*nserver:\s*(\S+)"],
        "cidr":          [r"^\s*CIDR:\s*(.+)$", r"^\s*inetnum:\s*(.+)$"],
        "netname":       [r"^\s*NetName:\s*(.+)$", r"^\s*netname:\s*(.+)$"],
    }
    result: dict = {}
    for line in raw.splitlines():
        for key, patterns in fields.items():
            for pat in patterns:
                m = re.match(pat, line, re.IGNORECASE)
                if m:
                    val = m.group(1).strip()
                    if key == "name_servers":
                        result.setdefault(key, []).append(val.lower())
                    elif key not in result:
                        result[key] = val
    if "name_servers" in result:
        result["name_servers"] = sorted(set(result["name_servers"]))
    return result


# ── nslookup ─────────────────────────────────────────────────────────────────────

def nslookup(domain: str, server: str = "", record_type: str = "A") -> dict:
    """Returns {raw, records: [...], reverse_dns?}."""
    domain = (domain or "").strip()
    if not domain:
        return {"raw": "", "records": []}

    is_ip = bool(re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", domain))

    if is_ip:
        try:
            host, aliases, ipaddrs = socket.gethostbyaddr(domain)
            return {
                "raw": f"PTR: {host}\nAliases: {aliases}\nIPs: {ipaddrs}",
                "records": [{"type": "PTR", "value": host}],
                "reverse_dns": host,
            }
        except Exception as e:
            return {"raw": f"[reverse lookup failed: {e}]", "records": []}

    if has("nslookup"):
        cmd = ["nslookup", "-type=" + record_type, domain]
        if server:
            cmd.append(server)
        raw = run_cmd(cmd, timeout=10)
    elif has("dig"):
        srv = [f"@{server}"] if server else []
        raw = run_cmd(["dig"] + srv + [domain, record_type, "+noall", "+answer"], timeout=10)
    else:
        raw = "[nslookup/dig not available]"

    records = _parse_nslookup(raw, record_type)
    if not records and record_type == "A":
        try:
            ip = socket.gethostbyname(domain)
            records.append({"type": "A", "value": ip})
        except Exception:
            pass

    return {"raw": raw, "records": records, "server": server or "system"}


def _parse_nslookup(out: str, record_type: str) -> list:
    records = []
    seen = set()

    if "ANSWER SECTION" in out:
        for line in out.splitlines():
            m = re.match(r"^\S+\s+\d+\s+IN\s+(\S+)\s+(.+)$", line)
            if m:
                t, v = m.group(1), m.group(2).strip()
                if (t, v) in seen:
                    continue
                seen.add((t, v))
                records.append({"type": t, "value": v})

    rtype = record_type.upper()
    in_answer = False
    for line in out.splitlines():
        if "Non-authoritative answer" in line or "Authoritative answer" in line or "answer:" in line.lower():
            in_answer = True
            continue
        if rtype == "A":
            m = re.match(r"^Address(?:es)?:\s*([\d.]+)$", line.strip())
            if m and in_answer and "#" not in line:
                key = ("A", m.group(1))
                if key not in seen:
                    seen.add(key)
                    records.append({"type": "A", "value": m.group(1)})
        elif rtype == "AAAA":
            m = re.match(r"^Address(?:es)?:\s*([0-9a-fA-F:]+)$", line.strip())
            if m and ":" in m.group(1) and in_answer:
                key = ("AAAA", m.group(1))
                if key not in seen:
                    seen.add(key)
                    records.append({"type": "AAAA", "value": m.group(1)})
        elif rtype == "MX":
            m = re.search(r"mail exchanger\s*=\s*(\d+)\s+(\S+)", line)
            if m:
                records.append({"type": "MX", "priority": int(m.group(1)), "value": m.group(2).rstrip(".")})
        elif rtype == "NS":
            m = re.search(r"nameserver\s*=\s*(\S+)", line)
            if m:
                records.append({"type": "NS", "value": m.group(1).rstrip(".")})
        elif rtype == "TXT":
            m = re.search(r'text\s*=\s*"(.+)"', line)
            if m:
                records.append({"type": "TXT", "value": m.group(1)})
        elif rtype == "CNAME":
            m = re.search(r"canonical name\s*=\s*(\S+)", line)
            if m:
                records.append({"type": "CNAME", "value": m.group(1).rstrip(".")})

    return records
