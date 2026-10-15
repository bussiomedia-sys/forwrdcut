"""Derive 9:16 punch-in crops for a locked-off two-shot.

Sketch and interview footage is often one static wide holding two people. At 9:16 that
reads small and static, and there is no coverage to cut to. This finds each subject and
prints the ffmpeg crop for a single on them, so you can pre-render punch-ins and cut the
dialogue like real coverage.

It locates subjects by TEMPORAL VARIANCE rather than face detection: on a locked-off
camera the only things that change frame to frame are the people. That needs no model
(OpenCV 5 dropped the Haar cascades) and it keeps working when a subject looks down,
turns away, or is in profile - all of which break a frontal face detector.

    python tools/two_shot_crops.py CLIP.MOV --start 14 --end 62
    python tools/two_shot_crops.py CLIP.MOV --preview /tmp/check   # writes crop previews

Prints ready-to-paste ffmpeg crop=W:H:X:Y values.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import numpy as np


def sample_gray(path: str, start: float, end: float, n: int, width: int = 240):
    """Decode `n` evenly spaced frames as small grayscale arrays via ffmpeg."""
    step = (end - start) / max(n - 1, 1)
    frames = []
    for i in range(n):
        t = start + i * step
        p = subprocess.run(
            ["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", path, "-frames:v", "1",
             "-vf", f"scale={width}:-1,format=gray", "-f", "rawvideo", "-"],
            capture_output=True)
        if p.returncode or not p.stdout:
            continue
        buf = np.frombuffer(p.stdout, dtype=np.uint8)
        h = buf.size // width
        if h:
            frames.append(buf[:h * width].reshape(h, width))
    if not frames:
        sys.exit("no frames decoded")
    return np.stack(frames).astype(np.float32)


def energy_span(profile: np.ndarray, keep: float = 0.90):
    """Contiguous span holding `keep` of the profile's energy, trimmed symmetrically.

    Using energy percentiles instead of the mask's raw min/max keeps one stray glint or a
    flickering light from stretching the box across the whole frame."""
    total = profile.sum()
    if total <= 0:
        return None
    c = np.cumsum(profile) / total
    tail = (1 - keep) / 2
    lo = int(np.searchsorted(c, tail))
    hi = int(np.searchsorted(c, 1 - tail))
    return (lo, max(hi, lo + 1))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("clip")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float, required=True)
    ap.add_argument("--samples", type=int, default=40)
    ap.add_argument("--fit", type=float, default=0.75,
                    help="fraction of the subject's height to keep, anchored at the head "
                         "(1.0 = full body, ~0.6 = medium shot cutting around the thigh)")
    ap.add_argument("--head-pad", type=float, default=0.10,
                    help="headroom above the subject, as a fraction of crop height")
    ap.add_argument("--preview", help="directory to write a preview frame per subject")
    a = ap.parse_args()

    # real (display) dimensions, after any rotation metadata is applied
    dims = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height", "-of", "csv=p=0", a.clip],
        capture_output=True, text=True).stdout.strip().split(",")
    rot = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream_side_data=rotation", "-of", "default=nw=1:nk=1", a.clip],
        capture_output=True, text=True).stdout.strip()
    W, H = int(dims[0]), int(dims[1])
    if rot and abs(float(rot.splitlines()[0])) == 90:
        W, H = H, W

    stack = sample_gray(a.clip, a.start, a.end, a.samples)
    sd = stack.std(axis=0)
    sh, sw = sd.shape
    # keep the pixels that actually move; the threshold rides the frame's own noise floor
    thr = max(np.percentile(sd, 88), sd.max() * 0.14)
    mask = sd > thr

    cols = mask.sum(axis=0).astype(float)
    cols /= max(cols.max(), 1)
    # split the frame between the two subjects at the quietest column in the middle third
    lo, hi = int(sw * 0.25), int(sw * 0.75)
    split = lo + int(np.argmin(np.convolve(cols[lo:hi], np.ones(5) / 5, mode="same")))

    print(f"source {W}x{H} (display)   analysis {sw}x{sh}   split x={split/sw:.2f}")
    sx, sy = W / sw, H / sh
    even = lambda v: max(2, int(v) // 2 * 2)

    for name, sl in (("left", slice(0, split)), ("right", slice(split, sw))):
        band = sd[:, sl] * mask[:, sl]        # variance energy for this subject only
        rows, colsp = band.sum(axis=1), band.sum(axis=0)
        vspan, hspan = energy_span(rows), energy_span(colsp)
        if vspan is None or hspan is None:
            print(f"  {name}: nothing moving - skipped")
            continue
        cx = (sl.start or 0) * sx + (hspan[0] + hspan[1]) / 2 * sx
        top, bot = vspan[0] * sy, vspan[1] * sy
        ch = min(H, max((bot - top) * a.fit / (1 - a.head_pad), H * 0.28))
        cw = ch * 9 / 16
        if cw > W:
            cw, ch = W, W * 16 / 9
        cy0 = min(max(top - ch * a.head_pad, 0), H - ch)
        cx0 = min(max(cx - cw / 2, 0), W - cw)
        cw, ch, cx0, cy0 = even(cw), even(ch), even(cx0), even(cy0)
        print(f"  {name:5s} subject y={int(top)}..{int(bot)} cx={int(cx)}  ->  "
              f"crop={cw}:{ch}:{cx0}:{cy0}   (punch {H/ch:.2f}x)")
        if a.preview:
            d = Path(a.preview); d.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["ffmpeg", "-v", "error", "-y", "-ss", f"{(a.start+a.end)/2:.2f}", "-i", a.clip,
                 "-frames:v", "1", "-vf", f"crop={cw}:{ch}:{cx0}:{cy0},scale=300:-1",
                 str(d / f"{Path(a.clip).stem}_{name}.jpg")], check=False)


if __name__ == "__main__":
    main()
