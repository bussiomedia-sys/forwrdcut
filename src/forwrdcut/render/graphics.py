"""Designed on-screen graphics for ads: CTA buttons, price/badge pills, star
ratings, and a progress bar. Each is a Pillow PNG composited via FFmpeg overlay
at a timed position. Brand-consistent (Inter + #EA6024), placed in safe zones.

EDP `overlays` entries (composited in a final pass over the finished video):
  {"type": "cta",      "text": "PRE-ORDER NOW", "start": 12, "end": 18, "position": "lower"}
  {"type": "badge",    "text": "SAVE $10",      "start": 0,  "end": 18, "position": "top-right"}
  {"type": "stars",    "rating": 4.6, "text": "4.6 from real players", "start": 2, "end": 7, "position": "upper"}
  {"type": "progress", "start": 0, "end": null}
"""
from __future__ import annotations

import math
from pathlib import Path

from .captions import _load_font


def _orange(cfg) -> str:
    return cfg.captions.get("highlight", "#EA6024")


def _font_path(cfg):
    f = cfg.captions.get("font")
    if f and f != "auto" and not Path(f).is_absolute():
        f = str(cfg.root / f)
    return f


def _star(draw, cx, cy, r, fill):
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rad = r if i % 2 == 0 else r * 0.42
        pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
    draw.polygon(pts, fill=fill)


def _cta(text, fw, cfg, font_p):
    from PIL import Image, ImageDraw
    size = int(fw * 0.052)
    font = _load_font(font_p, size, "ExtraBold")
    pad_x, pad_y = int(size * 1.1), int(size * 0.6)
    tmp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    txt = text.upper()
    bb = tmp.textbbox((0, 0), txt, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    w, h = tw + 2 * pad_x, th + 2 * pad_y
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=h // 2, fill=_orange(cfg))
    d.text((pad_x - bb[0], pad_y - bb[1]), txt, font=font, fill="#FFFFFF")
    return img


def _badge(text, fw, cfg, font_p):
    from PIL import Image, ImageDraw
    size = int(fw * 0.040)
    font = _load_font(font_p, size, "Bold")
    pad_x, pad_y = int(size * 0.7), int(size * 0.45)
    tmp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    txt = text.upper()
    bb = tmp.textbbox((0, 0), txt, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    w, h = tw + 2 * pad_x, th + 2 * pad_y
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=h // 2, fill="#111111")
    d.text((pad_x - bb[0], pad_y - bb[1]), txt, font=font, fill=_orange(cfg))
    return img


def _stars(rating, text, fw, cfg, font_p):
    from PIL import Image, ImageDraw
    sr = int(fw * 0.020)              # star radius
    gap = int(sr * 0.5)
    n = 5
    stars_w = n * (2 * sr) + (n - 1) * gap
    size = int(fw * 0.034)
    font = _load_font(font_p, size, "Bold") if text else None
    tmp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    tw = (tmp.textbbox((0, 0), text.upper(), font=font)[2] if text else 0)
    pad = int(sr * 0.8)
    w = stars_w + (int(sr * 0.8) + tw if text else 0) + 2 * pad
    h = 2 * sr + 2 * pad
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = pad + sr
    for _ in range(n):
        _star(d, cx, h / 2, sr, _orange(cfg))
        cx += 2 * sr + gap
    if text:
        bb = tmp.textbbox((0, 0), text.upper(), font=font)
        d.text((stars_w + pad + int(sr * 0.8), (h - (bb[3] - bb[1])) / 2 - bb[1]),
               text.upper(), font=font, fill="#FFFFFF", stroke_width=max(1, size // 12), stroke_fill="#000000")
    return img


def _callout(text, fw, cfg, font_p):
    """Big bold ad callout headline: all-caps Inter Black, white with one optional
    orange 'hot' word (mark it *like_this*), heavy black stroke for legibility over
    footage, word-wrapped and centered. Returns a tight PNG (positioned by caller)."""
    from PIL import Image, ImageDraw
    size = int(fw * 0.055)
    font = _load_font(font_p, size, "Black")
    orange = _orange(cfg)
    toks = []
    for w in text.upper().split():
        hot = w.startswith("*") and w.endswith("*")
        toks.append((w.strip("*"), hot))
    tmp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    space = tmp.textlength(" ", font=font)
    maxw = int(fw * 0.86)
    lines, cur, curw = [], [], 0.0
    for word, hot in toks:
        ww = tmp.textlength(word, font=font)
        add = ww + (space if cur else 0)
        if cur and curw + add > maxw:
            lines.append(cur); cur, curw = [(word, hot, ww)], ww
        else:
            cur.append((word, hot, ww)); curw += add
    if cur:
        lines.append(cur)
    asc, desc = font.getmetrics()
    lh = int((asc + desc) * 1.05)
    line_ws = [sum(w for _, _, w in ln) + space * (len(ln) - 1) for ln in lines]
    stroke = max(3, size // 10)
    pad = stroke * 2
    blockw = int(max(line_ws)) if line_ws else 1
    blockh = lh * len(lines)
    img = Image.new("RGBA", (blockw + 2 * pad, blockh + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    y = pad
    for ln, lw in zip(lines, line_ws):
        x = pad + (blockw - lw) / 2
        for word, hot, ww in ln:
            d.text((x, y), word, font=font, fill=(orange if hot else "#FFFFFF"),
                   stroke_width=stroke, stroke_fill="#000000")
            x += ww + space
        y += lh
    return img


def feature_callout(text, frame_size, cfg, *, position="lower-left", subtext=None):
    """Premium landing-page feature label: clean white chip + dark text + orange
    accent (matches forwrd.co). Returns a full-frame RGBA PNG (overlay at 0:0)."""
    from PIL import Image, ImageDraw
    fw, fh = frame_size
    font_p = _font_path(cfg)
    size = max(22, int(fh * 0.040))
    font = _load_font(font_p, size, "Bold")
    sub_font = _load_font(font_p, int(size * 0.62), "Medium") if subtext else None
    txt = text.upper()

    tmp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bb = tmp.textbbox((0, 0), txt, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    sw = sh = 0
    if subtext:
        sbb = tmp.textbbox((0, 0), subtext, font=sub_font)
        sw, sh = sbb[2] - sbb[0], sbb[3] - sbb[1]

    pad = int(size * 0.62)
    bar_w = max(4, int(size * 0.16))
    gap = int(size * 0.5)
    text_w = max(tw, sw)
    text_h = th + (int(size * 0.35) + sh if subtext else 0)
    chip_w = bar_w + gap + text_w + 2 * pad
    chip_h = text_h + 2 * pad

    img = Image.new("RGBA", (fw, fh), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    m = int(min(fw, fh) * 0.055)
    if position == "lower-center":
        x, y = (fw - chip_w) // 2, fh - chip_h - m
    elif position == "lower-right":
        x, y = fw - chip_w - m, fh - chip_h - m
    else:  # lower-left
        x, y = m, fh - chip_h - m

    r = int(chip_h * 0.22)
    d.rounded_rectangle([x + 3, y + 6, x + chip_w + 3, y + chip_h + 6], radius=r, fill=(0, 0, 0, 45))  # shadow
    d.rounded_rectangle([x, y, x + chip_w, y + chip_h], radius=r, fill=(255, 255, 255, 236))           # chip
    d.rounded_rectangle([x + pad, y + pad, x + pad + bar_w, y + chip_h - pad], radius=bar_w // 2, fill=_orange(cfg))
    tx = x + pad + bar_w + gap
    d.text((tx - bb[0], y + pad - bb[1]), txt, font=font, fill="#1A1A1A")
    if subtext:
        d.text((tx, y + pad + th + int(size * 0.35)), subtext, font=sub_font, fill="#6B6B6B")
    return img


def _pos_xy(position, gw, gh, fw, fh):
    m = int(fw * 0.06)
    return {
        "top-right": (fw - gw - m, int(fh * 0.14)),
        "top-left": (m, int(fh * 0.14)),
        "upper": ((fw - gw) // 2, int(fh * 0.15)),
        "center": ((fw - gw) // 2, (fh - gh) // 2),
        "lower": ((fw - gw) // 2, int(fh * 0.76) - gh),
    }.get(position, ((fw - gw) // 2, int(fh * 0.76) - gh))


def build_overlay_specs(overlays, frame_size, total_dur, cfg, tmpdir):
    """Render each overlay graphic and return ffmpeg overlay specs."""
    fw, fh = frame_size
    font_p = _font_path(cfg)
    tmpdir = Path(tmpdir)
    specs = []
    for i, ov in enumerate(overlays):
        typ = ov.get("type")
        if typ == "progress":
            from PIL import Image
            barh = max(5, int(fh * 0.006))
            img = Image.new("RGBA", (fw, barh), (0, 0, 0, 0))
            from PIL import ImageDraw
            ImageDraw.Draw(img).rectangle([0, 0, fw, barh], fill=ov.get("color", _orange(cfg)))
            png = tmpdir / f"ov_{i}_progress.png"
            img.save(png)
            # slide a full-width bar in from the left so it appears to fill L→R
            specs.append({"png": png, "x": f"(t/{total_dur:.3f}-1)*{fw}", "y": str(int(fh * 0.018)),
                          "enable": None})
            continue
        if typ == "cta":
            img = _cta(ov["text"], fw, cfg, font_p)
        elif typ == "badge":
            img = _badge(ov["text"], fw, cfg, font_p)
        elif typ == "stars":
            img = _stars(ov.get("rating", 5), ov.get("text", ""), fw, cfg, font_p)
        elif typ == "callout":
            img = _callout(ov["text"], fw, cfg, font_p)
        else:
            continue
        gw, gh = img.size
        png = tmpdir / f"ov_{i}_{typ}.png"
        img.save(png)
        x, y = _pos_xy(ov.get("position", "lower"), gw, gh, fw, fh)
        s, e = ov.get("start"), ov.get("end")
        enable = None
        if s is not None or e is not None:
            s = 0 if s is None else s
            enable = f"between(t,{s},{e})" if e is not None else f"gte(t,{s})"
        specs.append({"png": png, "x": str(int(x)), "y": str(int(y)), "enable": enable})
    return specs
