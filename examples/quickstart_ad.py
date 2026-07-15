"""Quickstart: build a short vertical ad end to end.

Self-contained — it synthesizes its own placeholder footage with ffmpeg, so it runs anywhere
the `forwrdcut` package and ffmpeg are installed, with no external assets:

    python examples/quickstart_ad.py

It demonstrates the core workflow: author an EDP (segments + timed overlays + a ducked music
bed), then render it. To make a real ad, swap the generated clips for your own footage and
rewrite the beats / callouts. See ../docs/ENGINE.md for the full EDP schema and ../AGENTS.md
for how to make the edit *good*.
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from forwrdcut.config import load_config
from forwrdcut.render.music_gen import ensure_beds
from forwrdcut.render.timeline import render_timeline


def _placeholder_clip(path: Path, color: str, seconds: float = 2.6) -> None:
    """Render a solid-color test clip that stands in for real footage. (No text baked in —
    the engine's overlays draw the on-screen copy; this just needs to be a valid clip.)"""
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi",
         "-i", f"color=c={color}:s=1080x1920:d={seconds}:r=30",
         "-pix_fmt", "yuv420p", str(path)],
        check=True, capture_output=True)


def build_edp(clips: dict[str, Path], bed: Path) -> dict:
    """A 3-beat vertical ad: hook -> benefit -> CTA, with centered callouts and a ducked bed."""
    return {
        "version": 1, "project": "quickstart", "platform": "meta",
        "goal": "Quickstart demo — a 3-beat vertical ad",
        "target": {"width": 1080, "height": 1920, "fps": 30},
        "mute_source": True, "auto_motion": True,
        "segments": [
            {"source": str(clips["hook"]), "in": 0, "out": 2.5, "role": "seg",
             "reframe": "cover", "caption": "none"},
            {"source": str(clips["feature"]), "in": 0, "out": 2.5, "role": "seg",
             "reframe": "cover", "caption": "none"},
            {"source": str(clips["cta"]), "in": 0, "out": 2.5, "role": "seg",
             "reframe": "cover", "caption": "none"},
        ],
        "overlays": [
            {"type": "callout", "text": "ONE BOLD *HOOK*", "position": "center",
             "start": 0.2, "end": 2.4},
            {"type": "callout", "text": "THE KEY *BENEFIT*", "position": "center",
             "start": 2.7, "end": 4.9},
            {"type": "cta", "text": "SHOP NOW · EXAMPLE.COM", "position": "lower",
             "start": 5.2, "end": 7.4},
        ],
        "music": {"file": str(bed), "gain": 0.15, "duck": False},
        "loudnorm": True, "transition": "cut", "sfx": [],
    }


def main() -> None:
    cfg = load_config()
    beds = ensure_beds(cfg.root / "assets" / "music")
    tmp = Path(tempfile.mkdtemp(prefix="forwrdcut_quickstart_"))
    clips = {"hook": tmp / "hook.mp4", "feature": tmp / "feature.mp4", "cta": tmp / "cta.mp4"}
    _placeholder_clip(clips["hook"], "0x1B2A4A")
    _placeholder_clip(clips["feature"], "0x2E7D5B")
    _placeholder_clip(clips["cta"], "0xEA6024")

    out = cfg.output_dir / "quickstart_9x16.mp4"
    res = render_timeline(build_edp(clips, beds["upbeat"]), out, cfg)
    print(f"-> {out}  ({res['resolution']}, {res['duration']:.1f}s)")


if __name__ == "__main__":
    main()
