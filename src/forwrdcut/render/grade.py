"""Color grading — a consistent, punchy brand look across mixed footage.

Mixed sources (iPhone, DJI, screen) grade differently and look "raw". A light
parametric grade (contrast + saturation + warmth + sharpen) unifies them and
makes them pop. Config-driven via `[grade]`; applied to footage only (captions
overlay afterward, so brand colors stay exact). Custom LUTs supported too.
"""
from __future__ import annotations

from pathlib import Path

# Tasteful, social-tuned grades. Filter strings (no leading comma).
GRADE_PRESETS = {
    "punch": ("eq=contrast=1.06:saturation=1.14:gamma=0.98,"
              "colorbalance=rm=0.03:bm=-0.03:rs=0.02:bs=-0.02,unsharp=5:5:0.5"),
    "warm":  ("eq=contrast=1.04:saturation=1.10,"
              "colorbalance=rm=0.05:bm=-0.05,unsharp=5:5:0.4"),
    "vibrant": ("eq=contrast=1.07:saturation=1.22:gamma=0.97,unsharp=5:5:0.6"),
    "clean": "eq=contrast=1.03:saturation=1.05,unsharp=5:5:0.3",
}


def grade_chain(cfg) -> str:
    """Return a grade filter snippet (no leading/trailing comma), or '' if off."""
    g = cfg.data.get("grade", {})
    if not g.get("enabled", True):
        return ""
    lut = g.get("lut")
    if lut:  # apply a .cube LUT if provided
        lut_path = Path(lut)
        if not lut_path.is_absolute():
            lut_path = cfg.root / lut
        if lut_path.exists():
            return f"lut3d='{lut_path.as_posix()}'"
    if g.get("filter"):
        return g["filter"]
    return GRADE_PRESETS.get(g.get("preset", "punch"), GRADE_PRESETS["punch"])
