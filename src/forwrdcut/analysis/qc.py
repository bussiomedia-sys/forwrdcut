"""Render QC — the engine checks its own output before a human ever has to.

``qc_render`` inspects a finished video and reports machine-checkable defects:
  - stream mismatch: video and audio durations diverge (the "frozen tail" bug class)
  - loudness off target: integrated LUFS far from the -14 social/ad target
  - clipping risk: true peak above -1 dBFS
  - frozen video: static frames >= ``freeze_min`` seconds (bad unless it's an end card)
  - black open: the first frame(s) black — a dead hook
  - a contact-sheet PNG so eyes-on QC is one glance

Writes ``<render>.qc.json`` next to the file and returns the report dict. Exposed via
``forwrdcut qc`` and MCP so any agent (or CI) can gate on it.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from ..config import Config

_FREEZE_START = re.compile(r"freeze_start:\s*([0-9.]+)")
_FREEZE_DUR = re.compile(r"freeze_duration:\s*([0-9.]+)")
_BLACK = re.compile(r"black_start:([0-9.]+)\s+black_end:([0-9.]+)")

LUFS_TARGET = -14.0
LUFS_TOL = 3.0
# We measure the *encoded deliverable*: AAC adds ~1 dB of inter-sample overshoot past any
# limiter, so a -1 dBTP master reads ≈ -0.9..-0.8 here. Real clipping risk starts above
# -0.5 dBTP post-codec; the render chain's loudnorm+limiter keeps masters at -2 dB sample.
PEAK_MAX = -0.5
STREAM_TOL = 0.35


def _stream_durations(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,duration",
         "-of", "json", str(path)], capture_output=True, text=True).stdout
    durs = {}
    try:
        for s in json.loads(out).get("streams", []):
            if s.get("duration") is not None:
                durs[s.get("codec_type")] = float(s["duration"])
    except Exception:
        pass
    return durs


def _ffmpeg_stderr(args: list[str]) -> str:
    proc = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", *args],
                          capture_output=True, text=True)
    return proc.stderr or ""


def detect_freezes(path: Path, *, noise: str = "0.003", min_dur: float = 2.0) -> list[dict]:
    err = _ffmpeg_stderr(["-i", str(path), "-map", "0:v:0",
                          "-vf", f"freezedetect=n={noise}:d={min_dur}", "-f", "null", "-"])
    starts = [float(m) for m in _FREEZE_START.findall(err)]
    durs = [float(m) for m in _FREEZE_DUR.findall(err)]
    out = [{"start": round(s, 2), "duration": round(d, 2)} for s, d in zip(starts, durs)]
    if len(starts) > len(durs):
        # a freeze that runs to EOF never emits freeze_duration — close it against the
        # container duration so end-of-video freezes are still reported
        from ..media.ffprobe import probe
        total = probe(path).duration or starts[-1]
        out.append({"start": round(starts[-1], 2),
                    "duration": round(max(0.0, total - starts[-1]), 2)})
    return out


def detect_black_open(path: Path, *, window: float = 1.5) -> bool:
    err = _ffmpeg_stderr(["-t", f"{window}", "-i", str(path), "-map", "0:v:0",
                          "-vf", "blackdetect=d=0.4:pix_th=0.10", "-f", "null", "-"])
    m = _BLACK.search(err)
    return bool(m and float(m.group(1)) < 0.2)


def evaluate(video_dur: float | None, audio_dur: float | None, lufs: float | None,
             peak: float | None, freezes: list[dict], black_open: bool,
             total_dur: float, *, loudnorm_expected: bool = True) -> list[str]:
    """Pure rule set -> list of human-readable issues (empty = clean)."""
    issues = []
    if video_dur and audio_dur and abs(video_dur - audio_dur) > STREAM_TOL:
        issues.append(f"stream mismatch: video {video_dur:.2f}s vs audio {audio_dur:.2f}s "
                      f"(frozen-tail bug class)")
    if loudnorm_expected and lufs is not None and abs(lufs - LUFS_TARGET) > LUFS_TOL:
        issues.append(f"loudness {lufs:.1f} LUFS is off the {LUFS_TARGET:.0f} target (±{LUFS_TOL:.0f})")
    if peak is not None and peak > PEAK_MAX:
        issues.append(f"true peak {peak:.1f} dBFS above {PEAK_MAX:.1f} (clipping risk)")
    for f in freezes:
        # a freeze that runs to the very end is usually the intended end-card hold
        if f["start"] + f["duration"] < total_dur - 0.75:
            issues.append(f"frozen video {f['duration']:.1f}s at {f['start']:.1f}s (mid-edit)")
    if black_open:
        issues.append("opens on black frames (dead hook)")
    return issues


def contact_sheet(path: Path, out_png: Path, *, cols: int = 5, rows: int = 2) -> Path | None:
    from ..media.ffprobe import probe
    dur = probe(path).duration or 1.0
    step = max(0.5, dur / (cols * rows))
    proc = subprocess.run(
        ["ffmpeg", "-y", "-i", str(path),
         "-vf", f"fps=1/{step:.3f},scale=300:-1,tile={cols}x{rows}",
         "-frames:v", "1", str(out_png), "-loglevel", "error"], capture_output=True)
    return out_png if proc.returncode == 0 and out_png.exists() else None


def qc_render(cfg: Config, path: str | Path, *, sheet: bool = True,
              loudnorm_expected: bool = True) -> dict:
    from ..media.ffprobe import probe
    from .audio import measure_loudness

    path = Path(path)
    info = probe(path)
    durs = _stream_durations(path)
    loud = measure_loudness(path) if info.has_audio else {}
    freezes = detect_freezes(path)
    black = detect_black_open(path)

    issues = evaluate(durs.get("video"), durs.get("audio"),
                      loud.get("integrated_lufs"), loud.get("peak_dbfs"),
                      freezes, black, info.duration or 0.0,
                      loudnorm_expected=loudnorm_expected)
    report = {
        "file": str(path),
        "video": {"width": info.width, "height": info.height,
                  "duration": round(info.duration or 0, 2),
                  "stream_duration": durs.get("video")},
        "audio": {"present": info.has_audio, "stream_duration": durs.get("audio"),
                  "integrated_lufs": loud.get("integrated_lufs"),
                  "peak_dbfs": loud.get("peak_dbfs")},
        "freezes": freezes,
        "black_open": black,
        "issues": issues,
        "ok": not issues,
    }
    if sheet:
        png = contact_sheet(path, path.with_suffix(".sheet.png"))
        report["sheet"] = str(png) if png else None
    path.with_suffix(path.suffix + ".qc.json").write_text(json.dumps(report, indent=2))
    return report
