"""Reframing filter chains for converting any aspect ratio to 9:16 (or other).

``cover`` is the reliable default (center smart-crop, zoom-to-fill). ``blur_pad``
fits the whole frame over a blurred zoomed copy — only used when the ``gblur``
filter is present in this ffmpeg build.
"""
from __future__ import annotations

from ..media.ffmpeg import list_filters


def cover_chain(w: int, h: int) -> str:
    """Zoom to fill the target and center-crop. Works for any source orientation."""
    return (
        f"scale={w}:{h}:force_original_aspect_ratio=increase,"
        f"crop={w}:{h},setsar=1"
    )


def blur_pad_chain(w: int, h: int, sigma: int = 20) -> str:
    """Fit the whole frame, centered, over a blurred fill of itself."""
    return (
        f"split[bg][fg];"
        f"[bg]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
        f"gblur=sigma={sigma}[bgb];"
        f"[fg]scale={w}:{h}:force_original_aspect_ratio=decrease[fgf];"
        f"[bgb][fgf]overlay=(W-w)/2:(H-h)/2,setsar=1"
    )


def tracked_chain(plan: dict) -> str:
    """Build a subject-tracked crop chain from a reframe_track crop plan."""
    sw, th, tw = plan["scaled_w"], plan["th"], plan["tw"]
    if plan["mode"] == "pan":
        x0, x1, dur = plan["x0"], plan["x1"], plan["dur"]
        xexpr = f"{x0}+({x1}-{x0})*(t/{dur})"   # comma-free linear pan over the segment
    else:
        xexpr = str(plan["x"])
    return f"scale={sw}:{th},crop={tw}:{th}:{xexpr}:0,setsar=1"


def reframe_chain(w: int, h: int, mode: str = "cover") -> str:
    if mode == "blur_pad" and "gblur" in list_filters():
        return blur_pad_chain(w, h)
    return cover_chain(w, h)
