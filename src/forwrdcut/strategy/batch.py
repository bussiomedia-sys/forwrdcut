"""Batch planning: "make me N TikToks from my footage."

Scans/uses the library, scores each clip's standalone viral potential, picks the
best, and produces N Edit Decision Plans. If fewer usable clips than N exist, it
pads with distinct *variants* of the strongest clip (different hook + highlight
ordering) so you still get N different edits.
"""
from __future__ import annotations

from pathlib import Path

from ..config import Config
from ..analysis.scoring import analyze_clip
from .planner import plan_from_analysis


def clip_score(analysis: dict) -> float:
    """Rough standalone-clip potential: best hook + best highlight + has-speech."""
    hooks = analysis.get("hooks") or []
    highlights = analysis.get("highlights") or []
    hs = hooks[0]["score"] if hooks else 0.0
    ms = highlights[0]["score"] if highlights else 0.0
    audio_bonus = 1.0 if analysis.get("has_audio") else 0.0
    enough = 1.0 if (analysis.get("duration") or 0) >= 6 else -2.0
    return round(hs + 0.3 * ms + audio_bonus + enough, 2)


def rank_clips(cfg: Config, clips: list[str] | None = None) -> list[dict]:
    """Analyze (cached) and rank candidate clips, best first."""
    if clips is None:
        from ..analysis.scan import scan_library
        clips = [c.path for c in scan_library(cfg)]
    ranked = []
    for path in clips:
        try:
            a = analyze_clip(cfg, path)
        except Exception as e:
            print(f"  ! skip {Path(path).name}: {e}")
            continue
        ranked.append({"path": path, "analysis": a, "score": clip_score(a)})
    ranked.sort(key=lambda r: -r["score"])
    return ranked


def make_batch(cfg: Config, *, platform: str = "tiktok", n: int = 3,
               trends: dict | None = None, seconds: float | None = None,
               clips: list[str] | None = None) -> list[dict]:
    ranked = rank_clips(cfg, clips)
    if not ranked:
        return []

    plans: list[dict] = []
    for r in ranked[:n]:
        plans.append(plan_from_analysis(cfg, r["analysis"], platform=platform,
                                        target_seconds=seconds, trends=trends))

    # Pad with distinct variants of the strongest clip if the library is thin.
    variant = 1
    while len(plans) < n:
        top = ranked[0]["analysis"]
        plans.append(plan_from_analysis(cfg, top, platform=platform,
                                        target_seconds=seconds, trends=trends,
                                        variant=variant))
        variant += 1
    return plans
