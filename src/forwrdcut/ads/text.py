"""Native on-screen text for paid social: the text people add in the Instagram / TikTok editors.

Ads that look made in the app read as posts, not ads. Every style here copies a real in-app text option,
set small (about 50px at 1080 wide, the size the app itself uses), lowercase by convention.

  ig_box_white   Instagram "Classic" with the background toggle on: black text on a white rounded box
  ig_box_dark    the same toggle, dark: white text on a translucent black box
  ig_plain       Instagram "Classic", no background: white with a soft shadow. Washes out on pale
                 footage; QC measures contrast and fails it when it can't be read
  outline        TikTok-style white text with a thin dark outline
  typewriter     Instagram "Typewriter": monospace on a white box
  brand_pill     the brand's highlight colour as the box, white text
  postit         a yellow sticky note, handwritten, tilted a few degrees: Motion's 2026 benchmarks list the
                 "post-it" as a top format for fashion and accessories

Lines are balanced: one line if it fits, otherwise the fewest lines whose longest line is shortest,
and never a single leftover word on the last line.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .placements import RATIOS, overlap, safe_box

SF = "/System/Library/Fonts/SFNS.ttf"
TYPEWRITER = "/System/Library/Fonts/Supplemental/Courier New Bold.ttf"
_FALLBACKS = ["/System/Library/Fonts/Helvetica.ttc", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]

EMOJI_FONT = "/System/Library/Fonts/Apple Color Emoji.ttc"
EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\u2764]"
                   "[\uFE0F\u200D\U0001F000-\U0001FAFF\u2600-\u27BF\U0001F3FB-\U0001F3FF\u2764]*")
_emoji_cache: dict = {}

STYLES = ("ig_box_white", "ig_box_dark", "ig_plain", "outline", "typewriter", "brand_pill", "postit")
BOXED = {"ig_box_white", "ig_box_dark", "typewriter", "brand_pill", "postit"}
NOTE = "/System/Library/Fonts/Noteworthy.ttc"
SIZE = {"916": 50, "45": 46, "11": 44}


@dataclass
class TextLayer:
    text: str
    style: str
    ratio: str
    lines: list[str]
    box: tuple[int, int, int, int]            # where the text (and its box) lands in the frame
    png: Path
    fill: tuple = (255, 255, 255)
    meta: dict = field(default_factory=dict)


def _font(style: str, size: int, font: str | None = None):
    path = font or {"typewriter": TYPEWRITER, "postit": NOTE}.get(style, SF)
    for p in [path, *_FALLBACKS]:
        if Path(p).exists():
            f = ImageFont.truetype(p, size, index=1 if p == NOTE else 0)      # Noteworthy Bold
            if p == SF:
                try:
                    f.set_variation_by_name("Semibold")
                except Exception:
                    pass
            return f
    return ImageFont.load_default(size)


def _runs(line: str) -> list[tuple[str, bool]]:
    """Split a line into (text, is_emoji) runs."""
    out, i = [], 0
    for m in EMOJI.finditer(line):
        if m.start() > i:
            out.append((line[i:m.start()], False))
        out.append((m.group(), True))
        i = m.end()
    if i < len(line):
        out.append((line[i:], False))
    return out


def _emoji_img(seq: str, px: int) -> Image.Image | None:
    """Apple Color Emoji only ships bitmaps at fixed sizes, so draw at 160 and scale."""
    key = (seq, px)
    if key in _emoji_cache:
        return _emoji_cache[key]
    if not Path(EMOJI_FONT).exists():
        return None
    f = ImageFont.truetype(EMOJI_FONT, 160)
    im = Image.new("RGBA", (400, 220), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((10, 10), seq, font=f, embedded_color=True)
    bb = im.getbbox()
    if not bb:
        return None
    im = im.crop(bb)
    im = im.resize((max(1, round(im.width * px / im.height)), px), Image.LANCZOS)
    _emoji_cache[key] = im
    return im


def measure(draw, s: str, font) -> float:
    size = getattr(font, "size", 50)
    return sum(draw.textlength(r, font=font) if not e else size * 1.12 for r, e in _runs(s))


def draw_line(cv: Image.Image, cx: float, cy: float, line: str, font, fill, *, emoji: bool = True, **kw):
    """Draw one centred line with colour emoji inline (the in-app editors render emoji in colour)."""
    d = ImageDraw.Draw(cv)
    size = getattr(font, "size", 50)
    x = cx - measure(d, line, font) / 2
    for run, is_e in _runs(line):
        if not is_e:
            d.text((x, cy), run, font=font, fill=fill, anchor="lm", **kw)
            x += d.textlength(run, font=font)
            continue
        im = _emoji_img(run, int(size * 1.02)) if emoji else None
        if im is not None:
            cv.alpha_composite(im, (int(x + size * 0.05), int(cy - im.height / 2)))
        x += size * 1.12


def wrap_balanced(text: str, measure, max_w: float, max_lines: int = 3) -> list[str]:
    """Fewest lines that fit; among those, the split with the shortest longest line. No orphan word."""
    words = text.split()
    if measure(text) <= max_w or len(words) < 3:
        return [text]
    best = None
    for n in range(2, max_lines + 1):
        for cuts in combinations(range(1, len(words)), n - 1):
            idx = (0, *cuts, len(words))
            lines = [" ".join(words[a:b]) for a, b in zip(idx, idx[1:])]
            if len(words[idx[-2]:]) < 2:                     # last line would be one word
                continue
            widest = max(measure(ln) for ln in lines)
            if best is None or widest < best[0]:
                best = (widest, lines)
        if best and best[0] <= max_w:
            return best[1]
    return best[1] if best else [text]


def orphan_lines(lines: list[str]) -> bool:
    return len(lines) > 1 and len(lines[-1].split()) < 2


def place_y(ratio: str, block_h: float, avoid: list[tuple] | None = None, prefer: str = "top") -> float:
    """Centre y for a text block: inside the safe zone, as high as the preference asks, and moved off
    the product if the product is in the way."""
    _, y0, _, y1 = safe_box(ratio)
    w, _ = RATIOS[ratio]
    lo, hi = y0 + block_h / 2 + 10, y1 - block_h / 2 - 10
    anchors = {"top": [lo + 40, lo, (lo + hi) / 2, hi], "middle": [(lo + hi) / 2, lo + 40, hi],
               "bottom": [hi, (lo + hi) / 2, lo + 40]}[prefer]
    if not avoid:
        return anchors[0]
    best = min(anchors, key=lambda y: sum(overlap((w * 0.1, y - block_h / 2, w * 0.9, y + block_h / 2), a)
                                          for a in avoid))
    return best


def render_text(text: str, ratio: str, style: str = "ig_box_white", *, cache: Path,
                y: float | None = None, avoid: list[tuple] | None = None, prefer: str = "top",
                size: int | None = None, font: str | None = None, accent: str = "#F26F5E",
                width_frac: float = 0.84) -> TextLayer:
    if style not in STYLES:
        raise ValueError(f"unknown text style {style!r}; choose from {STYLES}")
    ow, oh = RATIOS[ratio]
    fs = size or (SIZE[ratio] + 8 if style == "postit" else SIZE[ratio])
    f = _font(style, fs, font)
    probe = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    lines = wrap_balanced(text, lambda s: measure(probe, s, f), ow * (0.62 if style == "postit" else width_frac))
    lh = int(fs * 1.28)
    pad_x, pad_y, r = (44, 34, 6) if style == "postit" else (26, 12, 22)
    block_h = lh * len(lines) + (2 * pad_y if style in BOXED else 0)
    cy = y if y is not None else place_y(ratio, block_h, avoid, prefer)
    y0 = cy - lh * len(lines) / 2

    cv = Image.new("RGBA", (ow, oh), (0, 0, 0, 0))
    widths = [measure(probe, ln, f) for ln in lines]
    fill = (255, 255, 255)
    if style == "postit":
        note_w = max(max(widths) + 2 * pad_x, 360)
        note = Image.new("RGBA", (int(note_w) + 60, int(block_h) + 60), (0, 0, 0, 0))
        nd = ImageDraw.Draw(note)
        nd.rectangle([30, 30, 30 + note_w, 30 + block_h], fill=(255, 233, 122, 255))
        nd.rectangle([30, 30, 30 + note_w, 30 + 14], fill=(247, 218, 96, 255))           # the sticky strip
        for i, ln in enumerate(lines):
            draw_line(note, 30 + note_w / 2, 30 + pad_y + lh * i + lh / 2, ln, f, (58, 44, 30, 255))
        shadow = Image.new("RGBA", note.size, (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rectangle([34, 38, 34 + note_w, 38 + block_h], fill=(0, 0, 0, 90))
        note = Image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(8)), note).rotate(
            -3, resample=Image.BICUBIC, expand=True)
        cv.alpha_composite(note, (int(ow / 2 - note.width / 2), int(cy - note.height / 2)))
        fill = (58, 44, 30)
        widths = [note_w - 2 * pad_x]
    elif style in BOXED:
        box_rgba = {"ig_box_white": (255, 255, 255, 255), "typewriter": (255, 255, 255, 255),
                    "ig_box_dark": (0, 0, 0, 158),
                    "brand_pill": tuple(int(accent.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)) + (255,)}[style]
        fill = (0, 0, 0) if style in ("ig_box_white", "typewriter") else (255, 255, 255)
        layer = Image.new("RGBA", cv.size, (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        for i, w in enumerate(widths):
            yc = y0 + lh * i + lh / 2
            ld.rounded_rectangle([ow / 2 - w / 2 - pad_x, yc - lh / 2 - pad_y + (6 if i else 0),
                                  ow / 2 + w / 2 + pad_x, yc + lh / 2 + pad_y - (6 if i < len(lines) - 1 else 0)],
                                 radius=r, fill=box_rgba[:3] + (255,))
        if box_rgba[3] < 255:
            layer.putalpha(layer.getchannel("A").point(lambda a: a * box_rgba[3] // 255))
        cv.alpha_composite(layer)
    elif style == "ig_plain":
        shd = Image.new("RGBA", cv.size, (0, 0, 0, 0))
        for i, ln in enumerate(lines):
            draw_line(shd, ow / 2, y0 + lh * i + lh / 2 + 2, ln, f, (0, 0, 0, 170), emoji=False)
        cv.alpha_composite(shd.filter(ImageFilter.GaussianBlur(6)))
        cv.alpha_composite(shd.filter(ImageFilter.GaussianBlur(16)))
    for i, ln in enumerate(lines if style != "postit" else []):
        kw = dict(stroke_width=3, stroke_fill=(20, 20, 20, 255)) if style == "outline" else {}
        draw_line(cv, ow / 2, y0 + lh * i + lh / 2, ln, f, fill + (255,), **kw)

    half = max(widths) / 2 + (pad_x if style in BOXED else 6)
    box = (int(ow / 2 - half), int(cy - block_h / 2), int(ow / 2 + half), int(cy + block_h / 2))
    cache.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(f"{text}|{ratio}|{style}|{cy:.0f}|{fs}|{font}|{accent}".encode()).hexdigest()[:12]
    png = cache / f"text_{style}_{ratio}_{key}.png"
    cv.save(png)
    return TextLayer(text, style, ratio, lines, box, png, fill)
