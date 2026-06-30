"""Audio analysis via FFmpeg filters.

- silence map (silencedetect) → dead-air to trim + speech regions
- integrated loudness + peak (ebur128) → normalization targets and energy

No extra Python deps; parses ffmpeg stderr. Cached by file hash.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from ..config import Config
from ..media.ffprobe import probe
from .. import project

_SIL_START = re.compile(r"silence_start:\s*([0-9.]+)")
_SIL_END = re.compile(r"silence_end:\s*([0-9.]+)")
_I_LUFS = re.compile(r"I:\s*(-?[0-9.]+)\s*LUFS")
_PEAK = re.compile(r"Peak:\s*(-?[0-9.]+)\s*dBFS")


def _ffmpeg_stderr(args: list[str]) -> str:
    proc = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", *args],
                          capture_output=True, text=True)
    return proc.stderr or ""


def detect_silence(path: str | Path, *, noise_db: float = -30.0, min_dur: float = 0.5) -> list[dict]:
    err = _ffmpeg_stderr([
        "-i", str(path), "-af", f"silencedetect=noise={noise_db}dB:d={min_dur}",
        "-f", "null", "-",
    ])
    starts = [float(m) for m in _SIL_START.findall(err)]
    ends = [float(m) for m in _SIL_END.findall(err)]
    regions = []
    for i, s in enumerate(starts):
        e = ends[i] if i < len(ends) else None
        regions.append({"start": round(s, 3), "end": round(e, 3) if e is not None else None})
    return regions


def measure_loudness(path: str | Path) -> dict:
    err = _ffmpeg_stderr(["-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"])
    i_vals = _I_LUFS.findall(err)
    peak_vals = _PEAK.findall(err)
    return {
        "integrated_lufs": float(i_vals[-1]) if i_vals else None,
        "peak_dbfs": float(peak_vals[-1]) if peak_vals else None,
    }


def analyze_audio(path: str | Path) -> dict:
    info = probe(path)
    if not info.has_audio:
        return {"has_audio": False, "silence": [], "loudness": {}}
    return {
        "has_audio": True,
        "silence": detect_silence(path),
        "loudness": measure_loudness(path),
    }


def analyze_audio_cached(cfg: Config, path: str | Path, *, force: bool = False) -> dict:
    path = Path(path)
    info = probe(path)
    con = project.connect(cfg.db_path)
    try:
        if not force:
            cached = project.get_analysis(con, str(path), "audio", info.file_hash)
            if cached is not None:
                return cached
        data = analyze_audio(path)
        project.save_analysis(con, str(path), "audio", info.file_hash, data)
        return data
    finally:
        con.close()
