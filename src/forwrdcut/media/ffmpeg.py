"""Typed FFmpeg subprocess wrapper.

Centralizes command execution, error surfacing (last lines of stderr), encoder
selection (VideoToolbox HW with libx264 fallback), and small format helpers.
"""
from __future__ import annotations

import shutil
import subprocess
from functools import lru_cache


class FFmpegError(RuntimeError):
    pass


def have(tool: str) -> bool:
    return shutil.which(tool) is not None


def assert_tools() -> None:
    missing = [t for t in ("ffmpeg", "ffprobe") if not have(t)]
    if missing:
        raise FFmpegError(f"Required tools missing from PATH: {', '.join(missing)}")


@lru_cache(maxsize=1)
def list_encoders() -> set[str]:
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True
    )
    names = set()
    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0][:1] in ("V", "A", "S"):
            names.add(parts[1])
    return names


@lru_cache(maxsize=1)
def list_filters() -> set[str]:
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True
    )
    names = set()
    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and len(parts[0]) <= 3:
            names.add(parts[1])
    return names


def pick_video_encoder(preferred: str = "h264_videotoolbox", fallback: str = "libx264") -> str:
    enc = list_encoders()
    if preferred in enc:
        return preferred
    if fallback in enc:
        return fallback
    raise FFmpegError(f"Neither {preferred} nor {fallback} available in this ffmpeg build")


def run(args: list[str], *, desc: str = "", check: bool = True,
        capture: bool = True) -> subprocess.CompletedProcess:
    """Run ffmpeg with -hide_banner -y prepended. Raises FFmpegError on failure."""
    cmd = ["ffmpeg", "-hide_banner", "-y", *args]
    proc = subprocess.run(cmd, capture_output=capture, text=True)
    if check and proc.returncode != 0:
        tail = "\n".join((proc.stderr or "").splitlines()[-30:])
        raise FFmpegError(
            f"ffmpeg failed{f' ({desc})' if desc else ''} [exit {proc.returncode}]:\n"
            f"{tail}\n\nCommand:\n  ffmpeg {' '.join(args)}"
        )
    return proc


def fmt_time(seconds: float) -> str:
    """Seconds -> ffmpeg-friendly HH:MM:SS.mmm."""
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"
