"""Emphasis detection — find the words a great editor would punch on.

A modern edit accents the *important* words: a quick scale-pop, push-in, or speed
bump on the payoff word. We infer emphasis from the transcript's word timing + form
(no audio decode required, though loudness can refine it): long/strong words, words
that end a thought, words after a pause, and de-emphasised filler.

``find_emphasis`` returns ranked emphasis moments; ``emphasis_pulses`` converts them to
per-segment pulse times (seconds from segment start) for the renderer's punch motion.
"""
from __future__ import annotations

import re

_STOP = {"the", "a", "an", "and", "or", "but", "so", "of", "to", "in", "on", "for",
         "is", "it", "i", "you", "we", "they", "that", "this", "with", "at", "as",
         "are", "was", "be", "by", "my", "your", "our", "me", "um", "uh", "like"}
_STRONG = re.compile(r"[!?]")
_WORD = re.compile(r"[A-Za-z']+")


def _word_text(w: dict) -> str:
    return (w.get("word") or w.get("text") or "").strip()


def _mid(w: dict) -> float:
    s, e = float(w.get("start", 0.0)), float(w.get("end", w.get("start", 0.0)))
    return (s + e) / 2.0


def score_word(prev: dict | None, w: dict) -> float:
    """How much a human editor would want to accent this word. Higher = punch it."""
    raw = _word_text(w)
    low = raw.lower().strip(".,!?;:")
    core = _WORD.findall(low)
    if not core:
        return 0.0
    token = core[0]
    letters = token.replace("'", "")       # count letters, not apostrophes
    dur = max(0.0, float(w.get("end", 0.0)) - float(w.get("start", 0.0)))
    score = 0.0
    if token in _STOP:
        score -= 1.5                       # never punch filler/glue words
    if len(letters) >= 6:
        score += 1.0                       # longer content words carry weight
    if raw.isupper() and len(token) > 1:
        score += 1.5                       # transcribed shouting / acronyms
    if _STRONG.search(raw):
        score += 1.5                       # ends a strong beat
    elif raw.endswith("."):
        score += 0.6
    if dur >= 0.32:
        score += 1.0                       # drawn-out = stressed in speech
    if prev is not None:
        gap = float(w.get("start", 0.0)) - float(prev.get("end", 0.0))
        if gap >= 0.30:
            score += 0.8                   # a beat of silence sets up the next word
    return score


def find_emphasis(words: list[dict], *, threshold: float = 1.4, min_spacing: float = 0.7,
                  max_per_10s: float = 3.0) -> list[dict]:
    """Ranked emphasis moments: [{time, word, score}], throttled so punches don't crowd."""
    if not words:
        return []
    cands = []
    for i, w in enumerate(words):
        if not _word_text(w):
            continue
        s = score_word(words[i - 1] if i else None, w)
        if s >= threshold:
            cands.append({"time": round(_mid(w), 3), "word": _word_text(w), "score": round(s, 2)})
    cands.sort(key=lambda c: c["time"])
    # enforce minimum spacing, keeping the stronger of two close candidates
    spaced: list[dict] = []
    for c in cands:
        if spaced and c["time"] - spaced[-1]["time"] < min_spacing:
            if c["score"] > spaced[-1]["score"]:
                spaced[-1] = c
            continue
        spaced.append(c)
    # global density cap
    if spaced:
        span = max(1.0, spaced[-1]["time"] - spaced[0]["time"])
        cap = max(1, int(max_per_10s * span / 10.0) + 1)
        if len(spaced) > cap:
            spaced = sorted(sorted(spaced, key=lambda c: -c["score"])[:cap], key=lambda c: c["time"])
    return spaced


def emphasis_pulses(words: list[dict], seg_start: float, seg_end: float, **kw) -> list[float]:
    """Emphasis times (seconds from segment start) for words inside [seg_start, seg_end)."""
    out = []
    for e in find_emphasis(words, **kw):
        if seg_start <= e["time"] < seg_end:
            out.append(round(e["time"] - seg_start, 3))
    return out
