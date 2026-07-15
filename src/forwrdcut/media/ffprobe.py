"""Typed ffprobe wrapper.

``probe(path)`` returns a :class:`MediaInfo` describing a video file. Display
dimensions account for rotation metadata (phone / gimbal footage), and a cheap
``file_hash`` (size + mtime + head bytes) keys the analysis cache without
hashing whole multi-GB files.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class MediaInfo:
    path: str
    filename: str
    size_bytes: int
    duration: float
    width: int          # display width (after rotation)
    height: int         # display height (after rotation)
    coded_width: int
    coded_height: int
    fps: float
    rotation: int       # normalized 0/90/180/270
    vcodec: str | None
    pix_fmt: str | None
    bitrate: int | None
    has_audio: bool
    acodec: str | None
    audio_channels: int | None
    audio_sample_rate: int | None
    aspect_ratio: float
    orientation: str    # landscape | portrait | square
    file_hash: str

    def to_dict(self) -> dict:
        return asdict(self)

    def summary(self) -> str:
        a = f"{self.acodec}/{self.audio_channels}ch" if self.has_audio else "no-audio"
        return (
            f"{self.filename}  {self.width}x{self.height} {self.orientation} "
            f"{self.fps:.2f}fps  {self.duration:.1f}s  {self.vcodec} {a}"
        )


class FFprobeError(RuntimeError):
    pass


def _run_ffprobe(path: Path) -> dict:
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise FFprobeError(f"ffprobe failed for {path}:\n{proc.stderr.strip()}")
    return json.loads(proc.stdout)


def _parse_fraction(s: str | None) -> float:
    if not s or s in ("0/0", "N/A"):
        return 0.0
    try:
        if "/" in s:
            n, d = s.split("/")
            return float(n) / float(d) if float(d) else 0.0
        return float(s)
    except (ValueError, ZeroDivisionError):
        return 0.0


def _rotation(stream: dict) -> int:
    rot = 0
    tags = stream.get("tags", {}) or {}
    if "rotate" in tags:
        try:
            rot = int(tags["rotate"])
        except (TypeError, ValueError):
            rot = 0
    for sd in stream.get("side_data_list", []) or []:
        if sd.get("side_data_type") == "Display Matrix" and sd.get("rotation") is not None:
            try:
                rot = int(round(float(sd["rotation"])))
            except (TypeError, ValueError):
                pass
    return rot % 360


def quick_hash(path: Path) -> str:
    """Cheap content-aware hash: size + mtime + first 256 KiB. Stable per edit."""
    st = path.stat()
    h = hashlib.sha1()
    h.update(str(st.st_size).encode())
    h.update(str(int(st.st_mtime)).encode())
    with open(path, "rb") as f:
        h.update(f.read(262144))
    return h.hexdigest()[:16]


def probe(path: str | Path) -> MediaInfo:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    data = _run_ffprobe(path)
    fmt = data.get("format", {})
    streams = data.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), None) or {}
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)

    duration = float(fmt.get("duration") or v.get("duration") or 0.0)
    cw = int(v.get("width") or 0)
    ch = int(v.get("height") or 0)
    rot = _rotation(v)
    if rot % 180 == 90:
        width, height = ch, cw
    else:
        width, height = cw, ch

    fps = _parse_fraction(v.get("avg_frame_rate")) or _parse_fraction(v.get("r_frame_rate"))
    bitrate = fmt.get("bit_rate") or v.get("bit_rate")
    aspect = (width / height) if height else 0.0
    orientation = "portrait" if height > width else "landscape" if width > height else "square"

    return MediaInfo(
        path=str(path),
        filename=path.name,
        size_bytes=int(fmt.get("size") or path.stat().st_size),
        duration=duration,
        width=width,
        height=height,
        coded_width=cw,
        coded_height=ch,
        fps=round(fps, 3),
        rotation=rot % 360,
        vcodec=v.get("codec_name"),
        pix_fmt=v.get("pix_fmt"),
        bitrate=int(bitrate) if bitrate else None,
        has_audio=a is not None,
        acodec=(a or {}).get("codec_name"),
        audio_channels=int((a or {}).get("channels")) if a and a.get("channels") else None,
        audio_sample_rate=int((a or {}).get("sample_rate")) if a and a.get("sample_rate") else None,
        aspect_ratio=round(aspect, 4),
        orientation=orientation,
        file_hash=quick_hash(path),
    )
