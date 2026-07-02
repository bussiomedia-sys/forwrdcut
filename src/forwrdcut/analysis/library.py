"""The footage library brain — semantic search + junk detection over the whole library.

The slowest step of every edit is *finding the shot*. This module turns the indexed
library (scan.py + cached transcripts) into something you can query:

    forwrdcut find --q "clamshell open paddles inside"

ranks every clip by how well its transcript + filename match, and returns the best
matching transcript *window with a timestamp* — so "find the moment he shows the fence
hooks" answers with `clip.mp4 @ 41.2s`, not just a filename.

Junk detection: clips whose speech matches none of the library's expected terms
(config `[library] expected_terms`, e.g. your brand/product words) are flagged —
mislabeled downloads get caught at index time instead of appearing mid-ad.

Search is deliberately dependency-free (token scoring, not embeddings): transcripts of
product footage are short and literal, and exact-word recall is what shot-finding needs.
A vision-embedding upgrade can slot in behind the same interface later.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..config import Config

_WORD = re.compile(r"[a-z0-9']+")

# glue words that carry no shot-finding signal
_STOP = {"the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "it", "is",
         "this", "that", "with", "at", "as", "i", "you", "we", "so", "my", "your"}


def _tokens(text: str) -> list[str]:
    return [t for t in _WORD.findall(text.lower()) if t not in _STOP]


def best_window(words: list[dict], qtokens: list[str], *, span: float = 8.0) -> dict | None:
    """Best ~span-second transcript window covering the most distinct query tokens.
    Returns {"start", "end", "text", "matched"} or None if nothing matches."""
    if not words or not qtokens:
        return None
    qset = set(qtokens)
    norm = [(_WORD.findall(w.get("word", "").lower()) or [""])[0] for w in words]
    best, best_score = None, 0
    for i, w in enumerate(words):
        t0 = float(w.get("start", 0.0))
        matched, j = set(), i
        while j < len(words) and float(words[j].get("end", t0)) - t0 <= span:
            if norm[j] in qset:
                matched.add(norm[j])
            j += 1
        score = len(matched)
        if score > best_score:
            text = " ".join(w.get("word", "") for w in words[i:j])
            best = {"start": round(t0, 2), "end": round(float(words[min(j, len(words)) - 1].get("end", t0)), 2),
                    "text": text.strip(), "matched": sorted(matched)}
            best_score = score
    return best


def score_clip(qtokens: list[str], transcript_tokens: set[str], filename: str) -> float:
    """Rank a clip for a query: distinct transcript matches dominate; filename helps."""
    if not qtokens:
        return 0.0
    qset = set(qtokens)
    t_hits = len(qset & transcript_tokens)
    f_tokens = set(_tokens(Path(filename).stem.replace("_", " ").replace("-", " ")))
    f_hits = len(qset & f_tokens)
    return t_hits * 2.0 + f_hits * 1.0


def _clip_transcript(cfg: Config, path: str) -> dict | None:
    """Cached transcript only (never transcribes during search). Past sessions cached
    under absolute OR working-dir-relative paths — try both keys."""
    from .. import project
    p = Path(path)
    keys = {str(p), str(p.resolve())}
    try:
        keys.add(str(p.resolve().relative_to(Path.cwd())))
    except ValueError:
        pass
    con = project.connect(cfg.db_path)
    try:
        for k in keys:
            tr = project.get_analysis(con, k, "transcript")
            if tr is not None:
                return tr
        return None
    finally:
        con.close()


def _iter_infos(cfg: Config, dirs: list[str] | None):
    """Clips to consider: explicit dirs (probed directly) or the indexed source library."""
    if dirs:
        from .scan import iter_videos
        from ..media.ffprobe import probe
        for d in dirs:
            for f in iter_videos(Path(d)):
                try:
                    yield probe(f)
                except Exception:
                    continue
    else:
        from .scan import scan_library
        yield from scan_library(cfg)


def find(cfg: Config, query: str, *, limit: int = 8, dirs: list[str] | None = None,
         transcribe_missing: bool = False) -> list[dict]:
    """Search the library (or explicit dirs). Ranked clips with best-window timestamps."""
    qtokens = _tokens(query)
    results = []
    for info in _iter_infos(cfg, dirs):
        path = info.path
        tr = _clip_transcript(cfg, path)
        if tr is None and transcribe_missing and info.has_audio:
            from .transcribe import transcribe_cached
            try:
                tr = transcribe_cached(cfg, path)
            except Exception:
                tr = None
        words = (tr or {}).get("words") or []
        t_tokens = set(_tokens(" ".join(w.get("word", "") for w in words)))
        score = score_clip(qtokens, t_tokens, path)
        if score <= 0:
            continue
        hit = best_window(words, qtokens)
        results.append({"path": path, "score": round(score, 1),
                        "duration": info.duration,
                        "orientation": "landscape" if (info.width or 0) >= (info.height or 0) else "vertical",
                        "hit": hit})
    results.sort(key=lambda r: (-r["score"], r["path"]))
    return results[:limit]


def audit(cfg: Config, *, expected_terms: list[str] | None = None,
          dirs: list[str] | None = None) -> list[dict]:
    """Flag likely-junk clips: speech present but ZERO expected terms in the transcript.
    Terms default to config [library] expected_terms. Speechless clips are skipped
    (b-roll is legitimate); untranscribed clips are reported as 'unindexed'."""
    terms = [t.lower() for t in
             (expected_terms or cfg.data.get("library", {}).get("expected_terms", []))]
    if not terms:
        return []
    flagged = []
    for info in _iter_infos(cfg, dirs):
        tr = _clip_transcript(cfg, info.path)
        if tr is None:
            flagged.append({"path": info.path, "reason": "unindexed (no cached transcript)"})
            continue
        words = tr.get("words") or []
        if len(words) < 12:            # little/no speech -> b-roll, fine
            continue
        text = " ".join(w.get("word", "") for w in words).lower()
        if not any(t in text for t in terms):
            flagged.append({"path": info.path,
                            "reason": f"speech matches none of the expected terms "
                                      f"({len(words)} words) — possible mislabeled junk"})
    return flagged
