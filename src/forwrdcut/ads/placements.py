"""Meta / Instagram placements: output sizes and the parts of the frame the app's UI covers.

A 9:16 ad runs in Reels *and* Stories, so its safe zone is the strictest of the two. A 4:5 ad runs in Feed,
where the video itself is mostly clear but the sound toggle, tags and the bottom gradient still sit on it.
Values are pixels at 1080 wide and are data, not code: when Meta moves its UI, change them here and every
builder, caption placer and QC check follows.
"""
from __future__ import annotations

RATIOS: dict[str, tuple[int, int]] = {"916": (1080, 1920), "45": (1080, 1350), "11": (1080, 1080)}

# Pixels of each edge the platform UI can cover. Meta's ads guide (fetched 2026-09-25) gives Reels and,
# since spring 2026, Stories the same zone: keep 14% of the top, 35% of the bottom and 6% of each side
# free of text and logos. On 1080x1920 that is 269 / 672 / 65.
PLACEMENTS: dict[str, dict] = {
    "reels":   {"ratio": "916", "top": 269, "bottom": 672, "left": 65, "right": 65},
    "stories": {"ratio": "916", "top": 269, "bottom": 672, "left": 65, "right": 65},
    "feed":    {"ratio": "45", "top": 100, "bottom": 250, "left": 60, "right": 60},
    "feed_sq": {"ratio": "11", "top": 80, "bottom": 200, "left": 60, "right": 60},
}

# The Reels action rail (like / comment / share / audio) sits on the right, above the bottom zone.
RAIL = {"916": (1080 - 150, 1920 - 1150, 1080, 1920 - 670)}


# A 9:16 master that will also be centre-cropped to 4:5 (y 285-1635) keeps its text in this box.
CROP_SAFE_916 = (65, 285, 1015, 1248)


def safe_box(ratio: str) -> tuple[int, int, int, int]:
    """(x0, y0, x1, y1) that no placement using this ratio covers."""
    w, h = RATIOS[ratio]
    zones = [p for p in PLACEMENTS.values() if p["ratio"] == ratio]
    top = max(z["top"] for z in zones)
    bottom = max(z["bottom"] for z in zones)
    left = max(z["left"] for z in zones)
    right = max(z["right"] for z in zones)
    return left, top, w - right, h - bottom


def ui_boxes(ratio: str) -> list[tuple[int, int, int, int]]:
    """Rectangles the UI covers, for drawing on review sheets and testing text collisions."""
    w, h = RATIOS[ratio]
    x0, y0, x1, y1 = safe_box(ratio)
    boxes = [(0, 0, w, y0), (0, y1, w, h), (0, y0, x0, y1), (x1, y0, w, y1)]
    if ratio in RAIL:
        boxes.append(RAIL[ratio])
    return boxes


def overlap(a: tuple, b: tuple) -> float:
    """Area of intersection of two (x0, y0, x1, y1) boxes."""
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return float(max(0, w) * max(0, h))
