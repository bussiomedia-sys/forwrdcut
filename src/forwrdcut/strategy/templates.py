"""Templates — CapCut's killer mechanic, done autonomously.

A ForwrdCut template is a **parameterized, beat-timed EDP**: a named structure with media
*slots*, a music bed, beat timing, and caption/overlay/look defaults. You supply clips; the
template fills the slots, times cuts to the beat, and renders. "Drop footage, ship."

Factories are PURE (build an EDP dict from clip metadata) so they're unit-tested without media
I/O; ``render_template`` does the probing + rendering.
"""
from __future__ import annotations

from pathlib import Path

from ..config import Config
from ..render.music_gen import STYLES

ASPECTS = {"9x16": (1080, 1920), "16x9": (1920, 1080), "1x1": (1080, 1080)}


def _slot_window(duration: float | None, slot: float) -> tuple[float, float]:
    """Pick a `slot`-second window from a clip (centered), clamped to its length."""
    if not duration or duration <= slot:
        return 0.0, round(slot, 3)
    start = round((duration - slot) / 2.0, 3)
    return start, round(start + slot, 3)


def beat_slideshow(clips: list[dict], *, bpm: float, target: tuple[int, int],
                   beats_per_clip: int = 2, music_file: str, captions: str = "none",
                   look: dict | None = None, fps: int = 30) -> dict:
    """Each clip becomes one beat-timed slot (default 2 beats long) — fast, punchy, music-driven.
    ``clips`` = [{"path": str, "duration": float|None}]."""
    slot = beats_per_clip * 60.0 / max(1.0, bpm)
    segs = []
    for i, c in enumerate(clips):
        tin, tout = _slot_window(c.get("duration"), slot)
        segs.append({"source": c["path"], "in": tin, "out": tout, "role": "seg",
                     "reframe": "cover", "caption": captions,
                     "motion": "zoom_in" if i % 2 == 0 else "zoom_out"})
    edp = {
        "version": 1, "project": "tpl_beat_slideshow", "platform": "reels",
        "goal": "beat-synced slideshow from dropped clips",
        "target": {"width": target[0], "height": target[1], "fps": fps},
        "captions": {"mode": "auto", "style": "box-pop", "position": "lower"},
        "auto_motion": False, "emphasis": False, "mute_source": True,
        "segments": segs, "sfx": [],
        "music": {"file": music_file, "gain": 0.18, "duck": False}, "loudnorm": True,
    }
    if look:
        edp.update(look)
    return edp


def feature_showcase(clips: list[dict], headlines: list[str], *, target: tuple[int, int],
                     music_file: str, seconds_per: float = 2.5, look: dict | None = None,
                     fps: int = 30) -> dict:
    """Hook + feature beats with a bold callout per beat (the listicle/feature-breakdown format).
    ``headlines[i]`` may mark one word with *asterisks* for the orange accent."""
    segs, overlays, t = [], [], 0.0
    for i, c in enumerate(clips):
        tin, tout = _slot_window(c.get("duration"), seconds_per)
        segs.append({"source": c["path"], "in": tin, "out": tout, "role": "seg",
                     "reframe": "cover", "caption": "none",
                     "motion": "punch" if i == 0 else ("zoom_in" if i % 2 else "zoom_out")})
        if i < len(headlines) and headlines[i]:
            overlays.append({"type": "callout", "text": headlines[i],
                             "position": "center" if i == 0 else "lower",
                             "start": round(t + 0.1, 2), "end": round(t + seconds_per - 0.05, 2)})
        t += seconds_per
    edp = {
        "version": 1, "project": "tpl_feature_showcase", "platform": "youtube",
        "goal": "feature-breakdown showcase from dropped clips",
        "target": {"width": target[0], "height": target[1], "fps": fps},
        "captions": {"mode": "auto", "style": "box-pop", "position": "lower"},
        "auto_motion": False, "mute_source": True, "segments": segs, "overlays": overlays,
        "sfx": [], "music": {"file": music_file, "gain": 0.16, "duck": True}, "loudnorm": True,
    }
    if look:
        edp.update(look)
    return edp


def photo_slideshow(photos: list[dict], *, bpm: float, target: tuple[int, int], music_file: str,
                    beats_per_photo: int = 4, titles: list[str] | None = None,
                    look: dict | None = None, fps: int = 30) -> dict:
    """Stills → a Ken Burns slideshow. Each photo dwells ``beats_per_photo`` beats (photos need
    longer than video clips to register) with an alternating slow push/pull, optional title
    callout per photo. ``photos`` = [{"path": str}]."""
    slot = beats_per_photo * 60.0 / max(1.0, bpm)
    titles = titles or []
    segs, overlays, t = [], [], 0.0
    for i, p in enumerate(photos):
        segs.append({"source": p["path"], "in": 0.0, "out": round(slot, 3), "role": "seg",
                     "reframe": "cover", "caption": "none",
                     "motion": "zoom_in" if i % 2 == 0 else "zoom_out"})
        if i < len(titles) and titles[i]:
            overlays.append({"type": "callout", "text": titles[i], "position": "lower",
                             "start": round(t + 0.2, 2), "end": round(t + slot - 0.2, 2)})
        t = round(t + slot, 2)
    edp = {"version": 1, "project": "tpl_photo_slideshow", "platform": "reels",
           "goal": "Ken Burns photo slideshow from dropped stills",
           "target": {"width": target[0], "height": target[1], "fps": fps},
           "captions": {"mode": "auto", "style": "box-pop", "position": "lower"},
           "auto_motion": False, "mute_source": True, "segments": segs, "overlays": overlays,
           "sfx": [], "music": {"file": music_file, "gain": 0.18, "duck": False}, "loudnorm": True}
    if look:
        edp.update(look)
    return edp


TEMPLATES = {"beat_slideshow": beat_slideshow, "feature_showcase": feature_showcase,
             "photo_slideshow": photo_slideshow}


def render_template(cfg: Config, name: str, clip_paths: list[str], out_path: str | Path, *,
                    aspect: str = "9x16", music_style: str = "driving",
                    headlines: list[str] | None = None, cinematic: bool = False, **opts) -> dict:
    """Probe clips, fill the named template, render. Returns the render result."""
    from ..media.ffprobe import probe
    from ..render.music_gen import ensure_beds
    from ..render.timeline import render_timeline

    if name not in TEMPLATES:
        raise ValueError(f"unknown template {name!r}; have {sorted(TEMPLATES)}")
    clips = [{"path": p, "duration": (probe(p).duration or None)} for p in clip_paths]
    target = ASPECTS.get(aspect, ASPECTS["9x16"])
    bed = ensure_beds(cfg.root / "assets" / "music").get(music_style)
    look = {"cinematic": True} if cinematic else None
    bpm = STYLES.get(music_style, STYLES["driving"])["bpm"]
    if name == "feature_showcase":
        edp = feature_showcase(clips, headlines or [], target=target, music_file=str(bed), look=look)
    elif name == "photo_slideshow":
        edp = photo_slideshow(clips, bpm=bpm, target=target, music_file=str(bed),
                              titles=headlines, look=look)
    else:
        edp = beat_slideshow(clips, bpm=bpm, target=target, music_file=str(bed), look=look)
    edp["project"] = Path(out_path).stem
    return render_timeline(edp, out_path, cfg)
