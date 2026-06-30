"""Caption rendering via Pillow → transparent PNG overlays.

Because this machine's FFmpeg lacks libfreetype/libass (no drawtext/subtitles),
captions are rasterized to RGBA PNGs and composited with the FFmpeg ``overlay``
filter. This gives full control over fonts, stroke, and per-word emphasis — and
is the foundation for word-by-word animated captions in Phase 3.

PIL is imported lazily so the rest of the package loads without it.
"""
from __future__ import annotations

from pathlib import Path

# Inter (FORWRD house font) first; bold system fonts as fallback.
_FONT_CANDIDATES = [
    str(Path(__file__).resolve().parents[3] / "assets" / "fonts" / "Inter-Variable.ttf"),
    "/System/Library/Fonts/Supplemental/Arial Black.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Impact.ttf",
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/System/Library/Fonts/Helvetica.ttc",
]


# Selectable caption looks. font_scale is a fraction of frame width; weight maps to
# an Inter named instance (Thin..Black). Sizes tuned for IG legibility.
CAPTION_STYLES: dict[str, dict] = {
    "box-pop":       {"font_scale": 0.070, "stroke_div": 10, "uppercase": True,  "highlight": True,  "highlight_style": "box",   "pop": True,  "max_words": 3, "weight": "Black"},
    "bold-pop":      {"font_scale": 0.072, "stroke_div": 10, "uppercase": True,  "highlight": True,  "highlight_style": "color", "pop": True,  "max_words": 3, "weight": "Black"},
    "karaoke":       {"font_scale": 0.064, "stroke_div": 11, "uppercase": True,  "highlight": True,  "highlight_style": "color", "pop": True,  "max_words": 5, "weight": "ExtraBold"},
    "clean-minimal": {"font_scale": 0.050, "stroke_div": 16, "uppercase": False, "highlight": False, "highlight_style": "color", "pop": False, "max_words": 4, "weight": "SemiBold"},
}


def find_font(preferred: str | None = None) -> str | None:
    if preferred and preferred != "auto" and Path(preferred).exists():
        return preferred
    for c in _FONT_CANDIDATES:
        if Path(c).exists():
            return c
    return None


def _load_font(font_path: str | None, size: int, weight: str | None = None):
    from PIL import ImageFont
    path = find_font(font_path)
    if path:
        try:
            font = ImageFont.truetype(path, size)
            if weight:  # set Inter variable-font weight (e.g. "Black", "SemiBold")
                for w in (weight, weight.encode()):
                    try:
                        font.set_variation_by_name(w)
                        break
                    except Exception:
                        continue
            return font
        except Exception:
            pass
    return ImageFont.load_default(size)


def _wrap(draw, text: str, font, max_w: int, stroke_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        trial = f"{cur} {w}".strip()
        bbox = draw.textbbox((0, 0), trial, font=font, stroke_width=stroke_width)
        if (bbox[2] - bbox[0]) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def render_caption_png(
    text: str,
    out_path: str | Path,
    *,
    frame_size: tuple[int, int] = (1080, 1920),
    style: str = "bold-pop",
    font_path: str | None = None,
    font_size: int | None = None,
    fill: str = "#FFFFFF",
    stroke: str = "#000000",
    position: str = "lower",          # lower | center | upper (within the safe band)
    safe_top_frac: float = 0.13,
    safe_bottom_frac: float = 0.24,
    safe_side_frac: float = 0.08,
    line_spacing: float = 1.14,
) -> Path:
    """Render a styled caption to a transparent PNG sized to *frame_size*,
    placed inside the IG-safe band (clear of top/bottom/side platform UI)."""
    from PIL import Image, ImageDraw

    sp = CAPTION_STYLES.get(style, CAPTION_STYLES["bold-pop"])
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fw, fh = frame_size
    if sp["uppercase"]:
        text = text.upper()

    size = font_size or max(28, int(fw * sp["font_scale"]))
    stroke_width = max(2, size // sp["stroke_div"])
    font = _load_font(font_path, size, sp.get("weight"))

    img = Image.new("RGBA", (fw, fh), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    max_w = int(fw * (1 - 2 * safe_side_frac))
    lines = _wrap(draw, text, font, max_w, stroke_width)

    # Measure block height.
    line_h = draw.textbbox((0, 0), "Ay", font=font, stroke_width=stroke_width)
    lh = (line_h[3] - line_h[1])
    step = int(lh * line_spacing)
    block_h = step * len(lines)

    top_lim = safe_top_frac * fh
    bot_lim = (1 - safe_bottom_frac) * fh
    if position == "center":
        y = top_lim + ((bot_lim - top_lim) - block_h) / 2
    elif position == "upper":
        y = top_lim
    else:  # lower = sit at the bottom of the safe band
        y = bot_lim - block_h
    y = int(max(top_lim, min(y, bot_lim - block_h)))

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font, stroke_width=stroke_width)
        w = bbox[2] - bbox[0]
        x = (fw - w) // 2 - bbox[0]
        draw.text(
            (x, y), line, font=font, fill=fill,
            stroke_width=stroke_width, stroke_fill=stroke,
        )
        y += step

    img.save(out_path)
    return out_path
