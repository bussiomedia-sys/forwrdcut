"""Highlight scoring + hook-line detection + the per-clip analysis orchestrator.

Combines transcript, scenes, and audio into:
  - ranked candidate *hook lines* (quotable openings) from the transcript
  - ranked *highlight windows* (sliding windows scored by speech density,
    scene-cut activity, and non-silence)

These feed the strategy engine (Phase 2). All caches are reused.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..config import Config
from ..media.ffprobe import probe
from .. import project
from .transcribe import transcribe_cached
from .scenes import detect_scenes_cached
from .audio import analyze_audio_cached

_HOOK_CUES = [
    "best", "#1", "number one", "only", "never", "secret", "top", "most",
    "why", "how", "stop", "don't", "free", "new", "worst", "biggest",
    "fastest", "easiest", "ever", "nobody", "everyone", "you need",
    "the truth", "selling", "industry", "game changer", "must",
]


def _sentences_from_words(words: list[dict]) -> list[dict]:
    """Reconstruct complete sentences (with timing) from word tokens, so hooks are
    whole sentences rather than Whisper's mid-sentence segment fragments."""
    sents, cur = [], []
    for w in words:
        cur.append(w)
        if w["word"][-1:] in ".?!":
            sents.append(cur)
            cur = []
    if cur:
        sents.append(cur)
    return [{"start": s[0]["start"], "end": s[-1]["end"],
             "text": " ".join(x["word"] for x in s).strip()} for s in sents if s]


def find_hook_lines(transcript: dict) -> list[dict]:
    words = transcript.get("words") or []
    units = (_sentences_from_words(words) if words else
             [{"start": s["start"], "end": s["end"], "text": s["text"]}
              for s in transcript.get("segments", [])])

    out: list[dict] = []
    for u in units:
        text = u["text"].strip()
        toks = text.split()
        wc = len(toks)
        if wc < 3:          # skip fragments ("I", "and so") — never a hook
            continue
        low = text.lower()
        low_toks = low.split()
        # Reject degenerate transcripts from music/ambient audio: repeated single
        # token ("I I I"), or no content word ≥4 chars.
        if len(set(low_toks)) < 3:
            continue
        if not any(len(w.strip(".,!?'")) >= 4 for w in low_toks):
            continue
        score = 0.0
        if 4 <= wc <= 12:
            score += 2.5     # tight, punchy = ideal hook length
        elif wc <= 18:
            score += 0.8
        else:
            score -= 0.5     # long/rambling openers underperform
        score += sum(1.2 for cue in _HOOK_CUES if cue in low)
        if re.search(r"\d", text):
            score += 1.0
        if text.endswith("?") or low.startswith(("how", "why", "what", "did you", "do you")):
            score += 1.5
        if not text.endswith((".", "?", "!")):
            score -= 0.5     # incomplete thought
        out.append({"start": round(u["start"], 3), "end": round(u["end"], 3),
                    "text": text, "words": wc, "score": round(score, 2)})

    if out:
        out[0]["score"] += 1.0  # the opening line makes a natural hook
    out.sort(key=lambda x: -x["score"])
    return out


def _in_silence(t: float, silence: list[dict]) -> bool:
    for r in silence:
        if r["end"] is None:
            if t >= r["start"]:
                return True
        elif r["start"] <= t <= r["end"]:
            return True
    return False


def score_highlights(transcript: dict, scenes: list[dict], audio: dict, duration: float,
                     *, window: float = 6.0, stride: float = 1.0) -> list[dict]:
    words = transcript.get("words", [])
    cuts = [s["start"] for s in scenes]
    silence = audio.get("silence", [])
    duration = max(duration, 0.1)
    window = min(window, duration)

    out: list[dict] = []
    t = 0.0
    while t + window <= duration + 1e-6 or not out:
        w0, w1 = t, min(t + window, duration)
        nwords = sum(1 for x in words if w0 <= x["start"] < w1)
        ncuts = sum(1 for c in cuts if w0 <= c < w1)
        samples = [w0 + i * ((w1 - w0) / 10 or 0.1) for i in range(10)]
        active = sum(1 for s in samples if not _in_silence(s, silence)) / 10.0
        score = nwords * 0.5 + ncuts * 1.5 + active * 2.0
        out.append({"start": round(w0, 2), "end": round(w1, 2), "score": round(score, 2),
                    "words": nwords, "cuts": ncuts, "active": round(active, 2)})
        if w1 >= duration:
            break
        t += stride
    out.sort(key=lambda x: -x["score"])
    return out


def top_nonoverlapping(windows: list[dict], n: int = 3) -> list[dict]:
    chosen: list[dict] = []
    for w in windows:
        if all(w["end"] <= c["start"] or w["start"] >= c["end"] for c in chosen):
            chosen.append(w)
        if len(chosen) >= n:
            break
    return chosen


def analyze_clip(cfg: Config, path: str | Path, *, force: bool = False) -> dict:
    path = Path(path)
    info = probe(path)
    if info.has_audio:
        transcript = transcribe_cached(cfg, path, force=force)
    else:
        transcript = {"segments": [], "words": [], "full_text": "", "language": None}
    scenes = detect_scenes_cached(cfg, path, force=force)
    audio = analyze_audio_cached(cfg, path, force=force)

    hooks = find_hook_lines(transcript)
    highlights = score_highlights(transcript, scenes, audio, info.duration)

    result = {
        "path": str(path),
        "filename": info.filename,
        "duration": info.duration,
        "orientation": info.orientation,
        "resolution": f"{info.width}x{info.height}",
        "has_audio": info.has_audio,
        "language": transcript.get("language"),
        "n_scenes": len(scenes),
        "scenes": scenes,
        "audio": audio,
        "hooks": hooks,
        "highlights": highlights,
        "transcript_text": transcript.get("full_text", ""),
    }
    con = project.connect(cfg.db_path)
    try:
        project.save_analysis(con, str(path), "analysis", info.file_hash, result)
    finally:
        con.close()
    return result
