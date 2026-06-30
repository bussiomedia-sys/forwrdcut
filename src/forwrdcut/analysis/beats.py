"""Beat detection + beat grids for beat-synced cutting.

Two paths:
  - ``beats_for_bed`` / ``beat_grid``: exact grid from a known BPM. Our procedural
    music beds (render/music_gen.py) have a known tempo, so cuts snap to a perfect grid.
  - ``detect_beats``: estimate beats from arbitrary audio (an onset-energy envelope +
    autocorrelation tempo + phase). Dependency-free beyond numpy + ffmpeg.

``snap_to_beats`` moves a list of intended cut times onto the nearest beat (within a
tolerance) so edits land musically. This is what makes a cut *feel* professionally timed.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np


def beat_grid(bpm: float, duration: float, *, offset: float = 0.0, subdivision: int = 1) -> list[float]:
    """Beat timestamps from ``offset`` to ``duration``. subdivision=2 → half-beats, etc."""
    if bpm <= 0 or duration <= 0:
        return []
    step = 60.0 / bpm / max(1, subdivision)
    n = int((duration - offset) / step) + 1
    return [round(offset + i * step, 4) for i in range(max(0, n)) if offset + i * step <= duration + 1e-6]


def downbeats(bpm: float, duration: float, *, offset: float = 0.0, beats_per_bar: int = 4) -> list[float]:
    """The first beat of each bar — the strongest accents to cut on."""
    return beat_grid(bpm / beats_per_bar, duration, offset=offset)


def beats_for_bed(style: str, duration: float, *, offset: float = 0.0) -> list[float]:
    """Exact beat grid for a procedural music bed of the given style."""
    from ..render.music_gen import STYLES
    bpm = STYLES.get(style, STYLES["upbeat"])["bpm"]
    return beat_grid(bpm, duration, offset=offset)


def snap_to_beats(times: list[float], beats: list[float], *, max_shift: float = 0.12) -> list[float]:
    """Snap each time to the nearest beat if within ``max_shift`` seconds; else leave it.

    Keeps cuts musical without destroying intentional timing (a cut far from any beat,
    e.g. a hard content boundary, is preserved)."""
    if not beats:
        return list(times)
    b = np.asarray(beats, dtype=float)
    out = []
    for t in times:
        j = int(np.argmin(np.abs(b - t)))
        out.append(round(float(b[j]), 4) if abs(b[j] - t) <= max_shift else round(float(t), 4))
    return out


# ---- detection from arbitrary audio -------------------------------------------------

def _decode_mono(path: str | Path, sr: int = 22050) -> np.ndarray:
    """Decode any audio/video file to a mono float32 array at ``sr`` via ffmpeg."""
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-loglevel", "error", "-i", str(path),
         "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"],
        capture_output=True)
    if proc.returncode != 0 or not proc.stdout:
        return np.zeros(0, dtype=np.float32)
    return np.frombuffer(proc.stdout, dtype="<i2").astype(np.float32) / 32768.0


def _onset_envelope(y: np.ndarray, sr: int, hop: int = 512) -> np.ndarray:
    """Half-wave-rectified energy flux — a cheap, robust onset strength signal."""
    if y.size < hop * 4:
        return np.zeros(0, dtype=np.float32)
    n = 1 + (len(y) - hop) // hop
    energy = np.empty(n, dtype=np.float32)
    for i in range(n):
        frame = y[i * hop:i * hop + hop]
        energy[i] = float(np.sqrt(np.mean(frame * frame)) + 1e-9)
    log_e = np.log1p(energy * 50.0)
    flux = np.diff(log_e, prepend=log_e[:1])
    return np.maximum(flux, 0.0)


def estimate_tempo(path: str | Path, *, sr: int = 22050, hop: int = 512,
                   bpm_range: tuple[float, float] = (60.0, 180.0)) -> float:
    """Estimate BPM via autocorrelation of the onset envelope. 0.0 if undetectable."""
    env = _onset_envelope(_decode_mono(path, sr), sr, hop)
    if env.size < 8:
        return 0.0
    env = env - env.mean()
    ac = np.correlate(env, env, mode="full")[env.size - 1:]
    fps = sr / hop
    lo = max(1, int(fps * 60.0 / bpm_range[1]))
    hi = min(len(ac) - 1, int(fps * 60.0 / bpm_range[0]))
    if hi <= lo:
        return 0.0
    lag = lo + int(np.argmax(ac[lo:hi]))
    return round(60.0 * fps / lag, 2) if lag else 0.0


def detect_beats(path: str | Path, duration: float | None = None, *, sr: int = 22050,
                 hop: int = 512) -> list[float]:
    """Estimate beat timestamps for arbitrary audio. Falls back to [] if undetectable."""
    y = _decode_mono(path, sr)
    if y.size < sr // 2:
        return []
    env = _onset_envelope(y, sr, hop)
    if env.size < 8:
        return []
    bpm = estimate_tempo(path, sr=sr, hop=hop)
    if bpm <= 0:
        return []
    total = duration if duration else len(y) / sr
    fps = sr / hop
    step = fps * 60.0 / bpm  # frames per beat
    # phase: align grid to the strongest onsets via cross-correlation over one beat
    best_phase, best_score = 0.0, -1.0
    for ph in np.linspace(0, step, 16, endpoint=False):
        idx = np.arange(ph, env.size, step).astype(int)
        idx = idx[idx < env.size]
        score = float(env[idx].sum())
        if score > best_score:
            best_score, best_phase = score, ph
    grid = beat_grid(bpm, total, offset=best_phase / fps)
    return grid
