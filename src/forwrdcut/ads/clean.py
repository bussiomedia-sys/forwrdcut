"""Remove a creator's static on-screen overlay (Instagram/TikTok icon + @handle) from UGC.

Meta down-ranks reposted, watermarked video, so creator footage has to be clean before it runs as a
brand ad. The overlay is the one white, thin-stroked thing that holds perfectly still while hands,
nails and products move: per short window, keep only near-white pixels that are lit in nearly every
frame, inside the boxes where the handle sits; keep text-sized blobs; inpaint them in every frame.

A semi-transparent fade (the overlay animating in or out) can't be inpainted cleanly: cut around it.
Always check the result by eye and with `find_residue`.

    from forwrdcut.ads.clean import remove_static_overlay
    remove_static_overlay(src, out, regions=[(410, 280, 720, 440, 215), (20, 690, 300, 820, 180)])
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import cv2
import numpy as np

Region = tuple[int, int, int, int, int]       # x0, y0, x1, y1, minimum brightness (V, 0-255)


def _white(frame: np.ndarray, regions: list[Region]) -> np.ndarray:
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    out = np.zeros(hsv.shape[:2], np.uint8)
    for x0, y0, x1, y1, vmin in regions:
        sub = hsv[y0:y1, x0:x1]
        out[y0:y1, x0:x1] = ((sub[..., 2] > vmin) & (sub[..., 1] < 70)).astype(np.uint8)
    return out


def remove_static_overlay(src: str | Path, out: str | Path, regions: list[Region], *, window: int = 10,
                          still: float = 0.9, max_h: int = 50, max_area: int = 2500) -> int:
    """Write a cleaned copy of `src` to `out` (H.264 CRF 12). Returns how many frames were touched."""
    cap = cv2.VideoCapture(str(src))
    fps = cap.get(cv2.CAP_PROP_FPS)
    frames = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        frames.append(f)
    cap.release()
    h, w = frames[0].shape[:2]
    masks = np.stack([_white(f, regions) for f in frames]).astype(np.float32)
    proc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}",
                             "-r", str(fps), "-i", "-", "-c:v", "libx264", "-crf", "12", "-preset", "medium",
                             "-pix_fmt", "yuv420p", str(out)], stdin=subprocess.PIPE)
    touched = 0
    k = np.ones((3, 3), np.uint8)
    for i, f in enumerate(frames):
        a, b = max(0, i - window // 2), min(len(frames), i + window // 2 + 1)
        static = (masks[a:b].mean(0) >= still).astype(np.uint8)
        n, lab, st, _ = cv2.connectedComponentsWithStats(static, 8)
        keep = np.isin(lab, [j for j in range(1, n) if st[j, cv2.CC_STAT_HEIGHT] <= max_h
                             and st[j, cv2.CC_STAT_AREA] <= max_area]).astype(np.uint8)
        if keep.any():
            touched += 1
            f = cv2.inpaint(f, cv2.dilate(keep, k, iterations=3) * 255, 5, cv2.INPAINT_TELEA)
        proc.stdin.write(f.tobytes())
    proc.stdin.close()
    proc.wait()
    return touched
