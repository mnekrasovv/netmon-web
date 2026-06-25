"""System info, interfaces, connections, ARP."""

from __future__ import annotations

import datetime
import os
import platform
import re
import socket
import sys
from pathlib import Path
from typing import Iterator

from .runner import IS_WINDOWS, has, run_cmd, stream_cmd


def sysinfo() -> dict:
    info = {
        "hostname": socket.gethostname(),
        "os": f"{platform.system()} {platform.release()}",
        "os_full": platform.version(),
        "arch": platform.machine(),
        "python": sys.version.split()[0],
        "now": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    if IS_WINDOWS:
        try:
            import ctypes
            ms = ctypes.windll.kernel32.GetTickCount64()
            uptime = datetime.timedelta(milliseconds=ms)
            info["uptime"] = str(uptime).split(".")[0]
        except Exception:
            info["uptime"] = ""
        try:
            import getpass
            info["user"] = f"{os.environ.get('USERDOMAIN', '')}\\{getpass.getuser()}"
        except Exception:
            info["user"] = ""
    else:
        try:
            with open("/proc/uptime") as f:
                secs = float(f.read().split()[0])
            info["uptime"] = str(datetime.timedelta(seconds=int(secs)))
        except Exception:
            info["uptime"] = ""
        try:
            for line in Path("/etc/os-release").read_text().splitlines():
                if line.startswith("PRETTY_NAME="):
                    info["distrib"] = line.split("=", 1)[1].strip().strip('"')
                    break
        except Exception:
            pass
        info["user"] = os.environ.get("USER", "")
    return info


def sysinfo_stream() -> Iterator[str]:
    info = sysinfo()
    yield "── СИСТЕМНАЯ ИНФОРМАЦИЯ ──"
    yield ""
    yield f"Дата/время  : {info.get('now', '')}"
    yield f"Hostname    : {info.get('hostname', '')}"
    yield f"ОС          : {info.get('os', '')} {info.get('os_full', '')}"
    if info.get("distrib"):
        yield f"Дистрибутив : {info['distrib']}"
    yield f"Архитектура : {info.get('arch', '')}"
    yield f"Python      : {info.get('python', '')}"
    if info.get("uptime"):
        yield f"Uptime      : {info['uptime']}"
    if info.get("user"):
        yield f"Пользователь: {info['user']}"


def interfaces_stream() -> Iterator[str]:
    yield "── СЕТЕВЫЕ ИНТЕРФЕЙСЫ И МАРШРУТИЗАЦИЯ ──"
    yield ""
    if IS_WINDOWS:
        yield "── ipconfig /all ──"
        yield from stream_cmd(["ipconfig", "/all"], timeout=20)
        yield ""
        yield "── route print ──"
        yield from stream_cmd(["route", "print"], timeout=20)
    else:
        if has("ip"):
            yield "── ip addr ──"
            yield from stream_cmd(["ip", "addr", "show"], timeout=10)
            yield ""
            yield "── ip route ──"
            yield from stream_cmd(["ip", "route", "show"], timeout=10)
        elif has("ifconfig"):
            yield "── ifconfig -a ──"
            yield from stream_cmd(["ifconfig", "-a"], timeout=10)
        try:
            yield ""
            yield "── /etc/resolv.conf ──"
            for line in Path("/etc/resolv.conf").read_text().splitlines():
                yield line
        except Exception:
            pass


def connections_stream() -> Iterator[str]:
    yield "── АКТИВНЫЕ СОЕДИНЕНИЯ ──"
    yield ""
    if IS_WINDOWS:
        out = run_cmd(["netstat", "-an"], timeout=15)
        yield "── Слушающие порты ──"
        for line in out.splitlines():
            if "LISTENING" in line:
                yield line
        yield ""
        yield "── Установленные соединения ──"
        for line in out.splitlines():
            if "ESTABLISHED" in line:
                yield line
    else:
        if has("ss"):
            yield "── ss -s ──"
            yield from stream_cmd(["ss", "-s"], timeout=10)
            yield ""
            yield "── ss -tuln ──"
            yield from stream_cmd(["ss", "-tuln"], timeout=10)
        elif has("netstat"):
            yield "── netstat -tuln ──"
            yield from stream_cmd(["netstat", "-tuln"], timeout=10)
        else:
            yield "[!] ss и netstat не найдены"


def arp_stream() -> Iterator[str]:
    yield "── ARP / СОСЕДИ ──"
    yield ""
    if IS_WINDOWS or has("arp"):
        yield from stream_cmd(["arp", "-a"], timeout=10)
    if not IS_WINDOWS and has("ip"):
        yield ""
        yield "── ip neigh ──"
        yield from stream_cmd(["ip", "neigh", "show"], timeout=10)
