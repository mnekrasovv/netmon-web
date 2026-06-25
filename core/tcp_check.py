"""TCP port connectivity check."""

from __future__ import annotations

import socket
import time

PORT_PRESETS = {
    "http": 80,
    "https": 443,
    "ssh": 22,
    "ftp": 21,
    "smtp": 25,
    "smtps": 465,
    "imap": 143,
    "imaps": 993,
    "pop3": 110,
    "pop3s": 995,
    "dns": 53,
    "rdp": 3389,
    "mysql": 3306,
    "postgres": 5432,
    "redis": 6379,
    "mongodb": 27017,
    "minecraft": 25565,
}


def check_port(host: str, port: int, timeout: float = 3.0) -> dict:
    """Returns {host, port, open: bool, time_ms, error}."""
    t0 = time.time()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return {
                "host": host,
                "port": port,
                "open": True,
                "time_ms": round((time.time() - t0) * 1000, 1),
            }
    except socket.timeout:
        return {
            "host": host, "port": port, "open": False,
            "time_ms": round((time.time() - t0) * 1000, 1),
            "error": "timeout",
        }
    except ConnectionRefusedError:
        return {
            "host": host, "port": port, "open": False,
            "time_ms": round((time.time() - t0) * 1000, 1),
            "error": "refused",
        }
    except socket.gaierror as e:
        return {
            "host": host, "port": port, "open": False,
            "time_ms": None, "error": f"dns: {e}",
        }
    except Exception as e:
        return {
            "host": host, "port": port, "open": False,
            "time_ms": round((time.time() - t0) * 1000, 1),
            "error": str(e)[:80],
        }


def check_ports(host: str, ports: list, timeout: float = 3.0) -> list:
    return [check_port(host, p, timeout) for p in ports]
