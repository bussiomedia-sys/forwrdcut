"""Speech transcription with word-level timestamps (faster-whisper).

The word timestamps are the backbone for caption sync and for locating quotable
hook lines. Results are cached in the SQLite analysis table keyed by file hash.
faster-whisper is imported lazily so the package loads without it.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from ..config import Config
from ..media.ffprobe import probe
from .. import project


@lru_cache(maxsize=2)
def _get_model(name: str, compute_type: str):
    from faster_whisper import WhisperModel
    # Apple Silicon: ctranslate2 runs on CPU; int8 is the fast/accurate sweet spot.
    return WhisperModel(name, device="cpu", compute_type=compute_type)


def transcribe(path: str | Path, cfg: Config) -> dict:
    tcfg = cfg.transcription
    model = _get_model(tcfg.get("model", "small"), tcfg.get("compute_type", "int8"))
    lang = tcfg.get("language") or None

    segments, info = model.transcribe(
        str(path),
        word_timestamps=True,
        language=lang,
        vad_filter=bool(tcfg.get("vad_filter", False)),
    )

    words: list[dict] = []
    seg_list: list[dict] = []
    for seg in segments:
        seg_list.append({"start": round(seg.start, 3), "end": round(seg.end, 3),
                         "text": seg.text.strip()})
        for w in (seg.words or []):
            token = w.word.strip()
            if token:
                words.append({"start": round(w.start, 3), "end": round(w.end, 3),
                              "word": token})

    return {
        "language": info.language,
        "duration": round(float(info.duration), 3),
        "segments": seg_list,
        "words": words,
        "full_text": " ".join(s["text"] for s in seg_list).strip(),
    }


def transcribe_cached(cfg: Config, path: str | Path, *, force: bool = False) -> dict:
    path = Path(path)
    info = probe(path)
    con = project.connect(cfg.db_path)
    try:
        if not force:
            cached = project.get_analysis(con, str(path), "transcript", info.file_hash)
            if cached:
                return cached
        data = transcribe(path, cfg)
        project.save_analysis(con, str(path), "transcript", info.file_hash, data)
        return data
    finally:
        con.close()


def words_in_range(words: list[dict], start: float, end: float) -> list[dict]:
    """Select words overlapping [start, end) and shift to segment-relative time."""
    out = []
    for w in words:
        if w["end"] > start and w["start"] < end:
            out.append({
                "start": round(max(0.0, w["start"] - start), 3),
                "end": round(min(end, w["end"]) - start, 3),
                "word": w["word"],
            })
    return out
