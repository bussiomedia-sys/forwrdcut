"""Ad QC: every check we used to do by eye, run on every file before a person sees the batch.

Per ad (FAIL blocks delivery, WARN is flagged on the sheet):
  spec        size matches the ratio; 48 kHz AAC; -14 LUFS (+/-1.5); no black first frame   FAIL
  length      3-30s; over 15s is flagged (the ads that win here are short)                  WARN
  safe zone   every piece of text clear of the Reels/Stories/Feed UI                        FAIL
  contrast    text without a box must stand out from the footage under it (>= 3:1)         FAIL
  orphan      no caption line that is a single leftover word                                FAIL
  copy        banned words, unapproved claims, em dashes (brand kit)                        FAIL
  frame one   product found and at least 22% of frame height in the first frame             WARN
  motion      something moves in the first half second (a still opener reads as a static ad) WARN
Per batch:
  diversity   two different edits that open on nearly the same frame. Meta's retrieval
              groups near-identical creatives, so they compete instead of testing           WARN

Writes `_qc/report.json` and `_qc/REVIEW SHEET (<ratio>).jpg`: frame one of every ad with the UI zones
shaded, a green / amber / red bar, and the first problem written under it.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from ..analysis.qc import detect_black_open
from . import framing
from .build import FOLDER, copy_issues
from .placements import RATIOS, safe_box, ui_boxes
from .text import BOXED, orphan_lines

LUFS_TARGET, LUFS_TOL = -14.0, 1.5
MIN_FILL = 0.22
MIN_CONTRAST = 3.0


def _probe(path: Path) -> dict:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                          "stream=codec_type,codec_name,width,height,sample_rate:format=duration",
                          "-of", "json", str(path)], capture_output=True, text=True).stdout
    j = json.loads(out)
    v = next((s for s in j["streams"] if s["codec_type"] == "video"), {})
    a = next((s for s in j["streams"] if s["codec_type"] == "audio"), {})
    return dict(w=v.get("width"), h=v.get("height"), acodec=a.get("codec_name"),
                sr=int(a.get("sample_rate", 0) or 0), dur=float(j["format"]["duration"]))


def _lufs(path: Path) -> float | None:
    err = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-af", "ebur128", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    m = re.findall(r"^\s+I:\s+(-?[0-9.]+) LUFS", err, re.M)
    return float(m[-1]) if m else None


def _frame(path: Path, t: float) -> np.ndarray | None:
    return framing.frame_at(path, t)


def _lum(rgb) -> float:
    c = np.asarray(rgb, float) / 255
    c = np.where(c <= 0.03928, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return float(0.2126 * c[..., 0] + 0.7152 * c[..., 1] + 0.0722 * c[..., 2]) if c.ndim == 1 else \
        0.2126 * c[..., 0] + 0.7152 * c[..., 1] + 0.0722 * c[..., 2]


def text_contrast(frame_bgr: np.ndarray, box, fill=(255, 255, 255)) -> float:
    """Contrast ratio between the text colour and the brighter part of the footage behind it (the
    80th percentile, so one pale patch under a word is enough to fail, as it is for a viewer)."""
    x0, y0, x1, y1 = (int(v) for v in box)
    h, w = frame_bgr.shape[:2]
    roi = frame_bgr[max(0, y0):min(h, y1), max(0, x0):min(w, x1)]
    if roi.size == 0:
        return 21.0
    bg = _lum(roi[..., ::-1])
    L_text = _lum(fill)
    L_bg = float(np.percentile(bg, 80 if L_text > 0.5 else 20))
    hi, lo = max(L_text, L_bg), min(L_text, L_bg)
    return (hi + 0.05) / (lo + 0.05)


def dhash(frame_bgr: np.ndarray) -> int:
    g = cv2.resize(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY), (9, 8))
    bits = (g[:, 1:] > g[:, :-1]).flatten()
    return int("".join("1" if b else "0" for b in bits), 2)


def opening_motion(path: Path, t1: float = 0.5) -> float:
    """How much the picture changes over the first `t1` seconds: camera travel (phase correlation, % of
    width) plus content change (mean absolute difference, 0-255), so a pan and a hand moving both count."""
    a, b = _frame(path, 0.02), _frame(path, t1)
    if a is None or b is None:
        return 0.0
    ga = cv2.cvtColor(cv2.resize(a, (216, 384)), cv2.COLOR_BGR2GRAY).astype(np.float32)
    gb = cv2.cvtColor(cv2.resize(b, (216, 384)), cv2.COLOR_BGR2GRAY).astype(np.float32)
    (dx, dy), _ = cv2.phaseCorrelate(ga, gb)
    return float(np.hypot(dx, dy) / 216 * 100 + np.mean(np.abs(ga - gb)) / 4)


MIN_OPEN_MOTION = 1.5


def check_ad(path: Path, side: dict | None, kit: dict) -> dict:
    fails, warns, info = [], [], {}
    p = _probe(path)
    ratio = (side or {}).get("ratio") or next((r for r, s in RATIOS.items() if s == (p["w"], p["h"])), None)
    info.update(ratio=ratio, dur=round(p["dur"], 2))
    if ratio is None or (p["w"], p["h"]) != RATIOS[ratio]:
        fails.append(f"size {p['w']}x{p['h']} is not a Meta ratio")
    if p["acodec"] != "aac" or p["sr"] != 48000:
        fails.append(f"audio {p['acodec']} {p['sr']} Hz (need AAC 48 kHz)")
    lufs = _lufs(path)
    info["lufs"] = lufs
    tol = LUFS_TOL + (2.5 if (side or {}).get("drop_at") else 0)   # a quiet intro before the drop reads low
    if lufs is None or abs(lufs - LUFS_TARGET) > tol:
        fails.append(f"loudness {lufs} LUFS (target {LUFS_TARGET})")
    if detect_black_open(path):
        fails.append("opens on black")
    if p["dur"] < 3 or p["dur"] > 30:
        warns.append(f"length {p['dur']:.1f}s outside 3-30s")
    elif p["dur"] > 15:
        warns.append(f"length {p['dur']:.1f}s (over 15s)")

    texts = (side or {}).get("texts", [])
    if ratio and texts:
        sx0, sy0, sx1, sy1 = safe_box(ratio)
        for t in texts:
            x0, y0, x1, y1 = t["box"]
            if x0 < sx0 or y0 < sy0 or x1 > sx1 or y1 > sy1:
                fails.append(f'"{t["text"]}" sits under the app UI')
            if orphan_lines(t["lines"]):
                fails.append(f'"{t["text"]}" leaves one word alone on its last line')
            if t["style"] not in BOXED:
                worst = min(text_contrast(fr, t["box"], tuple(t.get("fill", (255, 255, 255))))
                            for s in np.linspace(t["start"], max(t["start"], t["end"] - 0.1), 4)
                            if (fr := _frame(path, float(s))) is not None)
                info.setdefault("contrast", {})[t["text"]] = round(worst, 2)
                if worst < MIN_CONTRAST:
                    fails.append(f'"{t["text"]}" is hard to read ({worst:.1f}:1); use a text box')
        fails += copy_issues([t["text"] for t in texts], kit)

    mo = opening_motion(path)
    info["open_motion"] = round(mo, 2)
    if mo < MIN_OPEN_MOTION:
        warns.append(f"nothing moves in the first half second ({mo:.1f})")

    f0 = _frame(path, 0.05)
    sigs = framing.signatures(kit, (side or {}).get("products") or None)
    if f0 is not None:
        info["hash"] = dhash(f0)
        if sigs:
            fill = framing.fill(framing.product_box(f0, sigs))
            info["frame1_fill"] = round(fill, 2)
            if fill < MIN_FILL:
                warns.append(f"product only {fill:.0%} of frame height in frame one")
    return dict(file=str(path), status="FAIL" if fails else ("WARN" if warns else "PASS"),
                fails=fails, warns=warns, **info, ad=(side or {}).get("ad"))


def review_sheet(results: list[dict], out: Path, ratio: str) -> Path | None:
    rows = [r for r in results if r.get("ratio") == ratio]
    if not rows:
        return None
    ow, oh = RATIOS[ratio]
    tw = 216
    th = int(oh * tw / ow)
    cols = 5
    n = len(rows)
    sheet = Image.new("RGB", (cols * tw, ((n + cols - 1) // cols) * (th + 64)), "white")
    d = ImageDraw.Draw(sheet)
    try:
        F = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 13)
    except Exception:
        F = ImageFont.load_default()
    for i, r in enumerate(rows):
        fr = _frame(Path(r["file"]), 0.05)
        if fr is None:
            continue
        im = Image.fromarray(fr[..., ::-1]).convert("RGBA")
        shade = Image.new("RGBA", im.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(shade)
        for bx in ui_boxes(ratio):
            sd.rectangle(bx, fill=(255, 40, 40, 70))
        im = Image.alpha_composite(im, shade).convert("RGB").resize((tw - 6, th - 6))
        x, y = (i % cols) * tw, (i // cols) * (th + 64)
        sheet.paste(im, (x + 3, y + 3))
        col = {"PASS": (40, 170, 90), "WARN": (235, 160, 30), "FAIL": (220, 50, 50)}[r["status"]]
        d.rectangle([x + 3, y + th - 3, x + tw - 3, y + th + 3], fill=col)
        d.text((x + 4, y + th + 6), Path(r["file"]).stem[-30:], font=F, fill="black")
        note = (r["fails"] or r["warns"] or ["ok"])[0]
        d.text((x + 4, y + th + 24), note[:34], font=F, fill=col)
        if len(note) > 34:
            d.text((x + 4, y + th + 40), note[34:68], font=F, fill=col)
    sheet.save(out, quality=88)
    return out


def qc_batch(out_dir: str | Path, kit: dict | None = None) -> dict:
    out_dir = Path(out_dir)
    kit = kit or {}
    results = []
    for sub in FOLDER.values():
        for f in sorted((out_dir / sub).glob("*.mp4")):
            sc = out_dir / "_qc" / f"{f.stem}.json"
            side = json.loads(sc.read_text()) if sc.exists() else None
            results.append(check_ad(f, side, kit))
    # diversity: different edits that open on (nearly) the same picture
    for i, a in enumerate(results):
        for b in results[i + 1:]:
            if a.get("ratio") != b.get("ratio") or "hash" not in a or "hash" not in b:
                continue
            if a.get("ad") and a.get("ad") == b.get("ad"):
                continue                                  # text variants of one edit: expected
            if bin(a["hash"] ^ b["hash"]).count("1") <= 6:
                for r, o in ((a, b), (b, a)):
                    r["warns"].append(f"opens like {Path(o['file']).stem}")
                    if r["status"] == "PASS":
                        r["status"] = "WARN"
    qdir = out_dir / "_qc"
    qdir.mkdir(exist_ok=True)
    summary = {s: sum(r["status"] == s for r in results) for s in ("PASS", "WARN", "FAIL")}
    (qdir / "report.json").write_text(json.dumps(dict(summary=summary, results=results), indent=2))
    sheets = [review_sheet(results, qdir / f"REVIEW SHEET ({FOLDER[r]}).jpg", r) for r in RATIOS]
    return dict(summary=summary, results=results, sheets=[str(s) for s in sheets if s])
