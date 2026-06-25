"""Subprocess helpers: hard-timeout run + line streamer."""

from __future__ import annotations

import platform
import shutil
import subprocess
from typing import Iterator

IS_WINDOWS = platform.system() == "Windows"


def has(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def _decode(raw: bytes) -> str:
    encs = ("cp866", "cp1251", "utf-8", "latin-1") if IS_WINDOWS else ("utf-8", "latin-1")
    for enc in encs:
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, AttributeError):
            pass
    return raw.decode("ascii", errors="replace")


def run_cmd(cmd: list, timeout: int = 60) -> str:
    """Run command, return full output. Hard timeout via Popen + kill."""
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
            return _decode(stdout + stderr)
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                pass
            return "[таймаут]"
    except FileNotFoundError:
        return f"[команда не найдена: {cmd[0]}]"
    except Exception as e:
        return f"[ошибка: {e}]"


def stream_cmd(cmd: list, timeout: int = 120) -> Iterator[str]:
    """Run command, yield stdout/stderr lines as they come. Kills on timeout."""
    import threading
    import time

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    except FileNotFoundError:
        yield f"[команда не найдена: {cmd[0]}]"
        return
    except Exception as e:
        yield f"[ошибка: {e}]"
        return

    killed = {"v": False}

    def killer():
        time.sleep(timeout)
        if proc.poll() is None:
            killed["v"] = True
            proc.kill()

    t = threading.Thread(target=killer, daemon=True)
    t.start()

    try:
        assert proc.stdout is not None
        for raw_line in iter(proc.stdout.readline, b""):
            if not raw_line:
                break
            yield _decode(raw_line).rstrip("\r\n")
    finally:
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass

    if killed["v"]:
        yield "[таймаут]"
