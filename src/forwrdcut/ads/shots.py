"""Visual shot index: find usable product moments in silent footage by what's on screen.

The transcript search in `analysis.library` can't help with product b-roll, which has no speech. This
indexes every clip at a few samples per second:

  fill      how much of the frame height each product (brand-kit colour signature) takes
  motion    camera movement between samples (phase correlation, % of frame width per second), so a
            detailed but steady shot scores low and a whip pan or a re-grab scores high
  sharp     focus (variance of the Laplacian), so soft frames rank low
  text      share of near-white pixels in the middle of the frame: old burned-in captions from a
            previous ad. White props trip it too, so treat it as "look before using"
  hdr       HLG/PQ iPhone footage that needs tone-mapping before it matches SDR clips

and answers questions like "pretzel at least 35% of frame, steady, 3 seconds, no old text":

    forwrdcut shots-find "<folder>" --brand example --product pretzel --min-fill 0.35 --min-len 3

The index is cached per file (path + size + mtime), so re-running over a big library is instant.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import cv2
import numpy as np

from . import framing

VIDEO_EXT = {".mov", ".mp4", ".m4v"}
# Finished ads saved next to their footage (our own pm_/PM_ outputs, review folders) are not footage:
# they carry burned-in captions and would be re-cut into new ads.
EXCLUDE = ("pm_", "PM_")
EXCLUDE_DIRS = ("Ads to Review", "_MUSIC VARIANTS", "_qc")


INDEX_VERSION = 2


def _key(p: Path) -> str:
    st = p.stat()
    return hashlib.sha1(f"{p.resolve()}|{st.st_size}|{st.st_mtime}|{INDEX_VERSION}".encode()).hexdigest()[:16]


def _hdr(p: Path) -> bool:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=color_transfer", "-of", "csv=p=0", str(p)], capture_output=True, text=True)
    return out.stdout.strip() in ("arib-std-b67", "smpte2084")


def index_clip(p: Path, sigs: list[dict], sps: float = 4.0) -> dict:
    cap = cv2.VideoCapture(str(p))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    step = max(1, int(round(fps / sps)))
    samples, prev = [], None
    for i in range(n):
        if i % step:
            if not cap.grab():
                break
            continue
        ok, fr = cap.read()
        if not ok:
            break
        h, w = fr.shape[:2]
        small = cv2.resize(fr, (216, int(h * 216 / w)))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        g = np.float32(gray)
        if prev is not None:
            (dx, dy), _ = cv2.phaseCorrelate(prev, g)
            motion = float(np.hypot(dx, dy)) / g.shape[1] * 100 * sps     # % of width per second
        else:
            motion = 0.0
        prev = g
        hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
        mid = hsv[int(hsv.shape[0] * 0.25):int(hsv.shape[0] * 0.75)]
        white = float(np.mean((mid[..., 1] < 40) & (mid[..., 2] > 235)))
        fills = {}
        for sg in sigs:
            b = framing.product_box(fr, [sg])
            fills[sg["id"]] = round(framing.fill(b), 3)
        samples.append(dict(t=round(i / fps, 3), fill=fills, motion=round(motion, 2),
                            sharp=round(float(cv2.Laplacian(gray, cv2.CV_64F).var()), 1), text=round(white, 4)))
    w_, h_ = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    return dict(file=str(p), width=w_, height=h_, duration=round(n / fps, 3), hdr=_hdr(p), samples=samples)


def index_dir(folder: str | Path, kit: dict, cache: Path, *, recursive: bool = True, log=print) -> list[dict]:
    folder = Path(folder)
    sigs = framing.signatures(kit)
    cache.mkdir(parents=True, exist_ok=True)
    files = sorted(f for f in (folder.rglob("*") if recursive else folder.iterdir())
                   if f.suffix.lower() in VIDEO_EXT and not f.name.startswith(".")
                   and not f.name.startswith(EXCLUDE) and not any(d in f.parts for d in EXCLUDE_DIRS))
    out = []
    for f in files:
        sig_key = hashlib.sha1(json.dumps(sigs, sort_keys=True).encode()).hexdigest()[:8]
        c = cache / f"{_key(f)}_{sig_key}.json"
        if c.exists():
            out.append(json.loads(c.read_text()))
            continue
        try:
            rec = index_clip(f, sigs)
        except Exception as e:                               # an unreadable file shouldn't stop the index
            log(f"  skip {f.name}: {e}")
            continue
        c.write_text(json.dumps(rec))
        out.append(rec)
        log(f"  indexed {f.name} ({rec['duration']}s{', HDR' if rec['hdr'] else ''})")
    return out


def find_windows(index: list[dict], *, product: str | None = None, min_fill: float = 0.3,
                 min_len: float = 2.0, max_motion: float = 25.0, max_text: float = 0.02,
                 limit: int = 20) -> list[dict]:
    """Runs of consecutive samples where the product is big, the camera is steady enough and no old
    caption is on screen. Ranked by average fill x length, soft footage last."""
    hits = []
    for rec in index:
        s = rec["samples"]

        def good(x):
            f = x["fill"].get(product, 0) if product else max(x["fill"].values(), default=0)
            return f >= min_fill and x["motion"] <= max_motion and x["text"] <= max_text

        i = 0
        while i < len(s):
            if not good(s[i]):
                i += 1
                continue
            j = i
            while j + 1 < len(s) and good(s[j + 1]):
                j += 1
            t0, t1 = s[i]["t"], s[j]["t"] + (s[1]["t"] - s[0]["t"] if len(s) > 1 else 0)
            if t1 - t0 >= min_len:
                run = s[i:j + 1]
                fill = float(np.mean([(x["fill"].get(product, 0) if product else max(x["fill"].values()))
                                      for x in run]))
                hits.append(dict(file=rec["file"], start=t0, end=round(min(t1, rec["duration"]), 2),
                                 fill=round(fill, 2), motion=round(float(np.mean([x["motion"] for x in run])), 1),
                                 sharp=round(float(np.median([x["sharp"] for x in run])), 0), hdr=rec["hdr"],
                                 size=f"{rec['width']}x{rec['height']}"))
            i = j + 1
    sharp_floor = np.percentile([h["sharp"] for h in hits], 20) if hits else 0
    hits.sort(key=lambda h: (h["sharp"] >= sharp_floor, h["fill"] * min(h["end"] - h["start"], 6)), reverse=True)
    return hits[:limit]
