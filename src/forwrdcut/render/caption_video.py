"""Animated word-by-word caption frames (Pillow → PNG sequence).

Word-level timestamps drive a rolling group of words with the spoken word
emphasized. Premium touches: a subtle pop-in entrance per group, and a boxed
highlight (active word in a brand-orange rounded box). Rendered as a PNG
sequence and overlaid as one FFmpeg input — full control without libass.

Identical consecutive states are hard-linked, so few real renders even at 30fps.
"""
from __future__ import annotations

import math
import os
from pathlib import Path

from .captions import _load_font, CAPTION_STYLES


def chunk_words(words: list[dict], *, max_words: int = 3, max_gap: float = 0.7) -> list[dict]:
    """Group words into short phrases (≤max_words, split on long pauses)."""
    groups: list[list[dict]] = []
    cur: list[dict] = []
    for w in words:
        if cur and (len(cur) >= max_words or (w["start"] - cur[-1]["end"]) > max_gap):
            groups.append(cur)
            cur = [w]
        else:
            cur.append(w)
    if cur:
        groups.append(cur)
    return [{"start": g[0]["start"], "end": g[-1]["end"], "words": g} for g in groups]


def _active_group(groups: list[dict], t: float, hold: float = 0.4) -> dict | None:
    for i, g in enumerate(groups):
        nxt = groups[i + 1]["start"] if i + 1 < len(groups) else None
        end_show = nxt if nxt is not None else (g["end"] + hold)
        if g["start"] <= t < end_show:
            return g
    return None


def _state_key(g: dict | None, t: float) -> str:
    if not g:
        return "blank"
    active = next((i for i, w in enumerate(g["words"]) if w["start"] <= t < w["end"]), -1)
    rel = t - g["start"]
    pop = round(rel / 0.03) if rel < 0.18 else 99   # don't dedupe during the pop-in
    return f"{id(g)}:{active}:{pop}"


def build_caption_frames(
    words: list[dict],
    duration: float,
    fps: int,
    frame_size: tuple[int, int],
    out_dir: str | Path,
    *,
    style: str = "bold-pop",
    font_path: str | None = None,
    fill: str = "#FFFFFF",
    stroke: str = "#000000",
    highlight: str = "#FFE53B",
    position: str = "lower",
    safe_top_frac: float = 0.13,
    safe_bottom_frac: float = 0.24,
    safe_side_frac: float = 0.08,
) -> int:
    """Render the caption PNG sequence. Returns the number of frames written."""
    from PIL import Image, ImageDraw

    sp = CAPTION_STYLES.get(style, CAPTION_STYLES["bold-pop"])
    uppercase = sp["uppercase"]
    highlight_on = sp["highlight"]
    hstyle = sp.get("highlight_style", "color")   # color | box
    pop_on = sp.get("pop", False)
    max_words = sp["max_words"]

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fw, fh = frame_size
    size = max(32, int(fw * sp["font_scale"]))
    stroke_width = max(2, size // sp["stroke_div"])
    font = _load_font(font_path, size, sp.get("weight"))
    groups = chunk_words(words, max_words=max_words)

    measure = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    space_w = int(measure.textlength(" ", font=font))
    lh_box = measure.textbbox((0, 0), "Ay", font=font, stroke_width=stroke_width)
    line_h = lh_box[3] - lh_box[1]
    step = int(line_h * 1.2)
    pad = max(8, size // 6)
    max_w = int(fw * (1 - 2 * safe_side_frac)) - 2 * pad
    top_lim = safe_top_frac * fh
    bot_lim = (1 - safe_bottom_frac) * fh

    def layout(g):
        lines, cur, curw = [], [], 0
        for w in g["words"]:
            txt = w["word"].upper() if uppercase else w["word"]
            bb = measure.textbbox((0, 0), txt, font=font, stroke_width=stroke_width)
            ww = bb[2] - bb[0]
            add = ww + (space_w if cur else 0)
            if cur and curw + add > max_w:
                lines.append(cur)
                cur, curw = [(txt, w, ww)], ww
            else:
                cur.append((txt, w, ww))
                curw += add
        if cur:
            lines.append(cur)
        return lines

    def render_block(g, t):
        lines = layout(g)
        block_w = max((sum(ww for _, _, ww in ln) + space_w * (len(ln) - 1)) for ln in lines)
        block_w += 2 * pad
        block_h = step * len(lines) + 2 * pad
        blk = Image.new("RGBA", (block_w, block_h), (0, 0, 0, 0))
        d = ImageDraw.Draw(blk)
        y = pad
        for ln in lines:
            lw = sum(ww for _, _, ww in ln) + space_w * (len(ln) - 1)
            x = (block_w - lw) // 2
            for txt, w, ww in ln:
                active = highlight_on and (w["start"] <= t < w["end"])
                if active and hstyle == "box":
                    box = [int(x - pad * 0.5), int(y - pad * 0.2),
                           int(x + ww + pad * 0.5), int(y + line_h + pad * 0.5)]
                    d.rounded_rectangle(box, radius=max(6, pad // 2), fill=highlight)
                    d.text((x, y), txt, font=font, fill="#FFFFFF",
                           stroke_width=max(1, stroke_width // 3), stroke_fill=stroke)
                else:
                    d.text((x, y), txt, font=font, fill=(highlight if active else fill),
                           stroke_width=stroke_width, stroke_fill=stroke)
                x += ww + space_w
            y += step
        return blk

    def block_top(block_h):
        if position == "center":
            return top_lim + ((bot_lim - top_lim) - block_h) / 2
        if position == "upper":
            return top_lim
        return bot_lim - block_h

    def pop_scale(rel):
        if not pop_on or rel >= 0.15:
            return 1.0
        e = rel / 0.15
        return 0.86 + 0.14 * (1 - (1 - e) ** 2)   # ease-out to full size

    def render_state(g, t, path):
        img = Image.new("RGBA", (fw, fh), (0, 0, 0, 0))
        if g:
            blk = render_block(g, t)
            bw, bh = blk.size
            s = pop_scale(t - g["start"])
            if s != 1.0:
                blk = blk.resize((max(1, int(bw * s)), max(1, int(bh * s))), Image.Resampling.LANCZOS)
            cx, cy = fw / 2, block_top(bh) + bh / 2          # scale around the block center
            img.alpha_composite(blk, (int(cx - blk.size[0] / 2), int(cy - blk.size[1] / 2)))
        img.save(path)

    n = max(1, math.ceil(duration * fps))
    cache: dict[str, Path] = {}
    for i in range(n):
        t = i / fps
        g = _active_group(groups, t)
        key = _state_key(g, t)
        frame_path = out_dir / f"cap_{i:05d}.png"
        if key in cache:
            try:
                os.link(cache[key], frame_path)
                continue
            except OSError:
                pass
        render_state(g, t, frame_path)
        cache[key] = frame_path
    return n
