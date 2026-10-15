"""Product-aware framing: find the product in a shot and crop each placement around it.

Products are found by colour signature, declared per product in the brand kit, because a signature is
cheap, deterministic, and good enough for products with a distinctive colour:

    [products.pretzel]
    name = "Pretzel Charm"
    hues = [[5, 24]]        # OpenCV hue ranges, 0-180
    sat_min = 110
    val_min = 60

A kit without `[products]` still works: framing falls back to the centre of the frame, and QC skips
the product-size check.
"""
from __future__ import annotations

import cv2
import numpy as np

from .placements import RATIOS, safe_box

Box = tuple[float, float, float, float]        # normalised (x0, y0, x1, y1)


def signatures(kit: dict, only: list[str] | None = None) -> list[dict]:
    prods = kit.get("products", {}) or {}
    return [dict(id=k, **v) for k, v in prods.items() if not only or k in only]


def mask(frame_bgr: np.ndarray, sigs: list[dict], work_w: int = 270) -> np.ndarray:
    h, w = frame_bgr.shape[:2]
    small = cv2.resize(frame_bgr, (work_w, int(h * work_w / w)))
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    hh, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    m = np.zeros(hh.shape, bool)
    for sg in sigs:
        ok = ((s >= sg.get("sat_min", 90)) & (s <= sg.get("sat_max", 255))
              & (v >= sg.get("val_min", 60)) & (v <= sg.get("val_max", 255)))
        for lo, hi in sg.get("hues", []):
            m |= ok & (hh >= lo) & (hh <= hi)
    m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    return m.astype(bool)


def product_box(frame_bgr: np.ndarray, sigs: list[dict], min_area: float = 0.004) -> Box | None:
    """Union of the product-coloured blobs big enough to be a product, normalised to the frame."""
    if not sigs:
        return None
    m = mask(frame_bgr, sigs).astype(np.uint8)
    n, _, stats, _ = cv2.connectedComponentsWithStats(m, 8)
    area = m.shape[0] * m.shape[1]
    keep = [i for i in range(1, n) if stats[i, cv2.CC_STAT_AREA] >= min_area * area]
    if not keep:
        return None
    x0 = min(stats[i, 0] for i in keep)
    y0 = min(stats[i, 1] for i in keep)
    x1 = max(stats[i, 0] + stats[i, 2] for i in keep)
    y1 = max(stats[i, 1] + stats[i, 3] for i in keep)
    H, W = m.shape
    return x0 / W, y0 / H, x1 / W, y1 / H


def frame_at(src, t: float) -> np.ndarray | None:
    cap = cv2.VideoCapture(str(src))
    cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
    ok, fr = cap.read()
    cap.release()
    return fr if ok else None


def track(src, t0: float, t1: float, sigs: list[dict], n: int = 6) -> list[Box]:
    cap = cv2.VideoCapture(str(src))
    out = []
    for t in np.linspace(t0 + 0.05, max(t0 + 0.06, t1 - 0.1), n):
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, fr = cap.read()
        if ok:
            b = product_box(fr, sigs)
            if b:
                out.append(b)
    cap.release()
    return out


def source_size(src) -> tuple[int, int]:
    cap = cv2.VideoCapture(str(src))
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    return w, h


def plan_crop(src_w: int, src_h: int, ratio: str, boxes: list[Box], *, zoom: float = 1.0,
              aim_y: float | None = None) -> tuple[int, int, int, int]:
    """Static crop (x, y, w, h) in source pixels with the target aspect. The widest crop the source
    allows, tightened by `zoom`, placed so the product's centre lands in the middle of the placement's
    safe zone (or at `aim_y`, a fraction of the crop height). Always inside the source."""
    tw, th = RATIOS[ratio]
    a = tw / th
    cw, ch = (src_w, src_w / a) if src_w / src_h < a else (src_h * a, src_h)
    cw, ch = cw / max(zoom, 1.0), ch / max(zoom, 1.0)
    if boxes:
        cx = np.median([(b[0] + b[2]) / 2 for b in boxes]) * src_w
        cy = np.median([(b[1] + b[3]) / 2 for b in boxes]) * src_h
    else:
        cx, cy = src_w / 2, src_h / 2
    if aim_y is None:
        _, y0, _, y1 = safe_box(ratio)
        aim_y = (y0 + y1) / 2 / th
    x = float(np.clip(cx - cw / 2, 0, src_w - cw))
    y = float(np.clip(cy - aim_y * ch, 0, src_h - ch))
    return int(round(x)), int(round(y)), int(round(cw)) // 2 * 2, int(round(ch)) // 2 * 2


def fill(box: Box | None) -> float:
    """How much of the frame height the product takes (0 when not found)."""
    return 0.0 if not box else box[3] - box[1]
