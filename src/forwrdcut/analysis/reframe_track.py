"""Subject-tracked auto-reframe planning (OpenCV face detection).

For landscape→9:16 we must choose *where* to crop horizontally. This samples the
segment, finds the dominant face per sampled frame, and produces a crop plan:
either a static subject-centered crop or a gentle linear pan if the subject
drifts. Falls back to None (→ center cover) when the source isn't wider than the
target or no face is found.

OpenCV runs in a subprocess (it bundles its own libav, which clashes with PyAV
from faster-whisper if loaded in the same interpreter).
"""
from __future__ import annotations

import json
import statistics
import subprocess
import sys
from pathlib import Path

from ..config import Config
from ..media.ffprobe import probe

_WORKER = r"""
import json, sys, cv2
path, start, end, sample_fps = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
cap = cv2.VideoCapture(path)
fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
step = max(1, int(round(fps / max(sample_fps, 0.5))))
start_frame, end_frame = int(start * fps), int(end * fps)
cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
pts, src_w, src_h, fidx, i, nsamp = [], None, None, start_frame, 0, 0
while fidx <= end_frame:
    ok, frame = cap.read()
    if not ok:
        break
    if i % step == 0:
        nsamp += 1
        h, w = frame.shape[:2]
        src_w, src_h = w, h
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(gray, 1.1, 6, minSize=(int(w * 0.07), int(h * 0.07)))
        if len(faces):
            fx, fy, fw, fh = max(faces, key=lambda b: b[2] * b[3])
            pts.append([round((fidx - start_frame) / fps, 3), round(fx + fw / 2.0, 1)])
    fidx += 1
    i += 1
cap.release()
print(json.dumps({"src_w": src_w, "src_h": src_h, "points": pts, "samples": nsamp}))
"""


def compute_crop_plan(cfg: Config, clip: str | Path, start: float, end: float,
                      tw: int, th: int) -> dict | None:
    info = probe(clip)
    if not info.width or not info.height:
        return None
    target_aspect = tw / th
    if (info.width / info.height) <= target_aspect + 1e-3:
        return None  # not wider than target → center cover is correct

    rcfg = cfg.data.get("reframe", {})
    sample_fps = float(rcfg.get("sample_fps", 3.0))
    proc = subprocess.run(
        [sys.executable, "-c", _WORKER, str(clip), str(start), str(end), str(sample_fps)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    data = json.loads(proc.stdout.strip().splitlines()[-1])
    pts = data.get("points") or []
    samples = data.get("samples") or max(len(pts), 1)
    min_ratio = float(rcfg.get("min_face_ratio", 0.35))
    # Only trust tracking when a face appears consistently (real subject), else
    # fall back to center cover — avoids chasing false positives on b-roll.
    if not pts or (len(pts) / samples) < min_ratio:
        return None

    src_w = data.get("src_w") or info.width
    src_h = data.get("src_h") or info.height
    sx = th / src_h                      # uniform scale so height fills the target
    scaled_w = int(round(src_w * sx))
    scaled_w -= scaled_w % 2
    if scaled_w < tw:
        return None
    maxx = scaled_w - tw

    def to_x(cx: float) -> float:
        return min(max(cx * sx - tw / 2.0, 0.0), float(maxx))

    dur = max(0.1, end - start)
    half = dur / 2.0
    first = [to_x(cx) for t, cx in pts if t < half] or [to_x(pts[0][1])]
    second = [to_x(cx) for t, cx in pts if t >= half] or [to_x(pts[-1][1])]
    x0, x1 = statistics.median(first), statistics.median(second)
    overall = statistics.median([to_x(cx) for _, cx in pts])

    if rcfg.get("pan", True) and abs(x1 - x0) > 0.04 * scaled_w:
        return {"mode": "pan", "scaled_w": scaled_w, "th": th, "tw": tw,
                "x0": round(x0, 1), "x1": round(x1, 1), "dur": round(dur, 3),
                "faces": len(pts)}
    return {"mode": "static", "scaled_w": scaled_w, "th": th, "tw": tw,
            "x": round(overall, 1), "faces": len(pts)}
