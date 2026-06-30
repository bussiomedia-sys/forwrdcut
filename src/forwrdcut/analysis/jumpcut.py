"""Auto jump-cut editing — tighten talking clips by removing dead air + fillers.

Uses the word-level transcript to build maximal "speech windows": runs of words
with no long pause and no filler between them. Concatenating the windows yields
the fast, punchy jump-cut feel of good creator content. Pauses longer than
``max_gap`` and disfluencies ("um/uh") become cuts.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..config import Config
from .transcribe import transcribe_cached

DISFLUENCIES = {"um", "uh", "uhh", "umm", "uhm", "er", "erm", "mm", "hmm", "mhm", "ah", "eh"}
# aggressive set also trims weak filler words (can change meaning — opt-in)
SOFT_FILLERS = DISFLUENCIES | {"like", "basically", "literally", "actually", "so", "right", "yeah"}


def _clean(word: str) -> str:
    return re.sub(r"[^a-z']", "", word.lower())


def speech_windows(transcript: dict, *, max_gap: float = 0.45, pad: float = 0.06,
                   fillers: set[str] = DISFLUENCIES, min_win: float = 0.18) -> list[tuple[float, float]]:
    """Maximal keep-windows of speech; gaps > max_gap and fillers force a cut."""
    words = transcript.get("words") or []
    wins: list[list[float]] = []
    cur: list[float] | None = None
    for w in words:
        if _clean(w["word"]) in fillers:
            if cur:
                wins.append(cur)
                cur = None
            continue
        if cur is None:
            cur = [w["start"], w["end"]]
        elif w["start"] - cur[1] <= max_gap:
            cur[1] = w["end"]
        else:
            wins.append(cur)
            cur = [w["start"], w["end"]]
    if cur:
        wins.append(cur)

    out: list[tuple[float, float]] = []
    for a, b in wins:
        a, b = max(0.0, a - pad), b + pad
        if b - a >= min_win:
            out.append((round(a, 3), round(b, 3)))
    return out


def jumpcut_segments(cfg: Config, clip: str | Path, *, start: float = 0.0,
                     end: float | None = None, max_gap: float = 0.45, pad: float = 0.06,
                     aggressive: bool = False, max_total: float | None = None) -> list[tuple[float, float]]:
    """Return tightened keep-windows (optionally within [start,end], capped to max_total seconds)."""
    tr = transcribe_cached(cfg, clip)
    fillers = SOFT_FILLERS if aggressive else DISFLUENCIES
    wins = speech_windows(tr, max_gap=max_gap, pad=pad, fillers=fillers)
    clipped = []
    for a, b in wins:
        if end is not None and a >= end:
            continue
        if b <= start:
            continue
        a, b = max(a, start), (min(b, end) if end is not None else b)
        if b - a >= 0.18:
            clipped.append((round(a, 3), round(b, 3)))
    if max_total:
        kept, tot = [], 0.0
        for a, b in clipped:
            kept.append((a, b))
            tot += b - a
            if tot >= max_total:
                break
        clipped = kept
    return clipped


def jumpcut_stats(cfg: Config, clip: str | Path, **opts) -> dict:
    from ..media.ffprobe import probe
    wins = jumpcut_segments(cfg, clip, **opts)
    kept = round(sum(b - a for a, b in wins), 1)
    return {"windows": len(wins), "kept_seconds": kept,
            "source_seconds": round(probe(clip).duration, 1), "segments": wins}
