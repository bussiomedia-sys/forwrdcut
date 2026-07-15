"""One-call autonomous edit — drop in a raw clip, get a great Short.

Orchestrates the whole loop: analyze (transcribe + scenes + audio + hook/highlight
scoring) -> plan a hook-first jump-cut -> apply the world-class polish layer
(word-synced captions, motion on every shot, emphasis punches, a ducked procedural
music bed, beat-aligned cuts, loudness norm) -> render.

The polish layer is a pure function (``enrich_for_autoedit``) so it's unit-tested
without any media I/O.
"""
from __future__ import annotations

from pathlib import Path

from ..config import Config
from ..render.music_gen import STYLES


def beat_align_durations(segments: list[dict], bpm: float, *, max_shift: float = 0.12,
                         min_dur: float = 0.4) -> list[dict]:
    """Nudge each segment's out-point (≤ max_shift) so its OUTPUT cut lands on the music
    beat grid. Cuts that fall on the beat read as professionally timed. Tiny shifts only,
    so no words are lost."""
    if bpm <= 0:
        return segments
    beat = 60.0 / bpm
    acc = 0.0
    for s in segments:
        dur = s["out"] - s["in"]
        cut = acc + dur                              # intended output cut time
        nearest = round(cut / beat) * beat
        delta = nearest - cut
        if abs(delta) <= max_shift and dur + delta >= min_dur:
            s["out"] = round(s["out"] + delta, 3)
            dur += delta
        acc += dur
    return segments


def enrich_for_autoedit(edp: dict, music_file: str | Path, *, music_style: str = "driving",
                        target: dict | None = None, reframe: str = "cover",
                        beat_sync: bool = True) -> dict:
    """Apply the world-class polish layer to a planned EDP. Pure (no I/O)."""
    if target:
        edp["target"] = target
    pos = edp.get("captions", {}).get("position", "lower")
    edp["captions"] = {"mode": "auto", "style": "box-pop", "position": pos}
    edp["auto_motion"] = True          # life on every shot
    edp["emphasis"] = True             # punch the important words
    edp["loudnorm"] = True             # sit right in-feed
    edp.setdefault("mute_source", False)  # keep the speaker's audio; music ducks under it
    edp["sfx"] = []                    # no whoosh
    for s in edp.get("segments", []):
        s.setdefault("reframe", reframe)
        s.setdefault("caption", "auto")
    edp["music"] = {"file": str(music_file), "gain": 0.12, "duck": True}
    if beat_sync and edp.get("segments"):
        bpm = STYLES.get(music_style, STYLES["driving"])["bpm"]
        beat_align_durations(edp["segments"], bpm)
    return edp


def autoedit(cfg: Config, source: str | Path, out_path: str | Path, *, platform: str = "tiktok",
             target_seconds: float = 24.0, max_segments: int = 6, music_style: str = "driving",
             target: dict | None = None, reframe: str = "cover", beat_sync: bool = True) -> dict:
    """Analyze -> plan -> polish -> render. Returns the render result dict."""
    from ..analysis.scoring import analyze_clip
    from .planner import plan_from_analysis
    from ..render.music_gen import ensure_beds
    from ..render.timeline import render_timeline

    analysis = analyze_clip(cfg, source)
    edp = plan_from_analysis(cfg, analysis, platform=platform,
                             target_seconds=target_seconds, max_segments=max_segments)
    beds = ensure_beds(cfg.root / "assets" / "music")
    bed = beds.get(music_style) or next(iter(beds.values()))
    edp = enrich_for_autoedit(edp, bed, music_style=music_style, target=target,
                              reframe=reframe, beat_sync=beat_sync)
    edp["project"] = Path(out_path).stem
    edp["goal"] = f"autonomous {platform} short from {Path(source).name}"
    return render_timeline(edp, out_path, cfg)
