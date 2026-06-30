"""Rule-based strategy planner: analysis → Edit Decision Plan.

Encodes a baseline of the editing playbook with zero LLM dependency:
  - front-load the strongest hook line (open loop)
  - follow with the highest-scoring, non-overlapping payoff windows
  - trim toward the platform's length sweet spot
  - hard cuts with SFX cue slots; word-synced captions; music slot

If an Anthropic API key is present, `strategy.llm.refine_plan` can polish the
hook copy/ordering on top of this baseline (see plan_clip).
"""
from __future__ import annotations

from pathlib import Path

from ..config import Config
from ..analysis.scoring import analyze_clip, top_nonoverlapping

# Length sweet spots (seconds) by platform — overridable via trends/target_seconds.
PLATFORM_TARGETS = {"tiktok": 27, "reels": 30, "shorts": 35}


def _overlaps(a0: float, a1: float, b0: float, b1: float) -> bool:
    return a0 < b1 and b0 < a1


def plan_from_analysis(cfg: Config, analysis: dict, *, platform: str = "tiktok",
                       target_seconds: float | None = None, max_segments: int = 4,
                       trends: dict | None = None, variant: int = 0) -> dict:
    source = analysis["path"]
    reframe = ("smart" if cfg.data.get("reframe", {}).get("smart", False)
               else cfg.render.get("reframe_mode", "cover"))
    target_seconds = (target_seconds or (trends or {}).get("length_target")
                      or PLATFORM_TARGETS.get(platform, 27))

    hooks = analysis.get("hooks", [])
    highlights = top_nonoverlapping(analysis.get("highlights", []), 8)
    # variant>0 produces a distinct edit from the same clip: different hook + a
    # rotated highlight ordering.
    if variant and highlights:
        variant_rot = variant % len(highlights)
        highlights = highlights[variant_rot:] + highlights[:variant_rot]

    segments: list[dict] = []
    used: list[tuple[float, float]] = []
    hook_text, hook_why = "", ""

    if hooks:
        h = hooks[variant % len(hooks)]
        segments.append({"source": source, "in": round(h["start"], 2), "out": round(h["end"], 2),
                         "role": "hook", "reframe": reframe, "caption": "auto"})
        used.append((h["start"], h["end"]))
        hook_text = h["text"]
        hook_why = f"highest hook score ({h['score']}); front-loaded as the open loop"

    for w in highlights:
        if any(_overlaps(w["start"], w["end"], u0, u1) for u0, u1 in used):
            continue
        segments.append({"source": source, "in": round(w["start"], 2), "out": round(w["end"], 2),
                         "role": "payoff", "reframe": reframe, "caption": "auto"})
        used.append((w["start"], w["end"]))
        if sum(s["out"] - s["in"] for s in segments) >= target_seconds or len(segments) >= max_segments:
            break

    # Keep the hook first; order payoffs chronologically for narrative coherence.
    hook_seg = [s for s in segments if s["role"] == "hook"]
    payoffs = sorted((s for s in segments if s["role"] != "hook"), key=lambda s: s["in"])
    segments = hook_seg + payoffs

    # No transition SFX by default (whoosh-free). Clean hard cuts; add a music
    # bed / voiceover instead. (Cue points can still be added to an EDP by hand.)
    sfx = []

    caption_style = (trends or {}).get("caption_style") or cfg.captions.get("style", "bold-pop")
    return {
        "version": 1,
        "project": (f"{Path(source).stem.lower().replace(' ', '_')}_{platform}"
                    + (f"_v{variant}" if variant else "")),
        "platform": platform,
        "goal": (trends or {}).get("goal") or f"Viral {platform} clip — {cfg.brand.get('niche', '')}".strip(),
        "target": {"width": int(cfg.render.get("target_width", 1080)),
                   "height": int(cfg.render.get("target_height", 1920)),
                   "fps": int(cfg.render.get("fps", 30) or 30)},
        "hook": {"type": "spoken", "text": hook_text, "why": hook_why},
        "captions": {"mode": "auto", "style": caption_style, "position": "center"},
        "segments": segments,
        "sfx": sfx,
        "music": {"slot": True, "note": "add trending sound natively in-app (licensing)"},
        "trends": trends or None,
        "notes": "Rule-based plan from analysis. Edit freely, then `render-plan`.",
    }


def plan_clip(cfg: Config, clip: str | Path, *, platform: str = "tiktok",
              target_seconds: float | None = None, trends: dict | None = None,
              refine: bool = True, force: bool = False) -> dict:
    analysis = analyze_clip(cfg, clip, force=force)
    edp = plan_from_analysis(cfg, analysis, platform=platform,
                             target_seconds=target_seconds, trends=trends)
    if refine:
        try:
            from . import llm
            if llm.available():
                edp = llm.refine_plan(cfg, edp, analysis)
        except Exception as e:
            edp.setdefault("notes", "")
            edp["notes"] += f"  (LLM refine skipped: {e})"
    return edp
