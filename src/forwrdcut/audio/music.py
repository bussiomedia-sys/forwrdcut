"""Music library — licensed tracks as first-class citizens, procedural beds as fallback.

Drop real (licensed) music into ``assets/music/licensed/`` (gitignored — licensed audio
must never be committed/redistributed) or point ``[music] licensed_dir`` in config.toml
anywhere on disk. The library scans those files, detects BPM (analysis/beats.py) and
duration, infers a mood from filename tokens, and caches the metadata.

``pick_music(cfg, mood=..., min_duration=...)`` returns the best licensed track for the
brief, falling back to the built-in procedural beds so the engine always has *something*.
An EDP can now say ``"music": {"mood": "upbeat", "duck": true}`` instead of a file path;
the timeline resolves it at render time. The returned BPM feeds beat-aligned cutting.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..config import Config

AUDIO_EXTS = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".aiff", ".aif"}

# filename tokens -> canonical mood. "FORWRD_upbeat_summer_128bpm.mp3" -> "upbeat"
MOOD_TOKENS = {
    "upbeat": "upbeat", "happy": "upbeat", "fun": "upbeat", "pop": "upbeat",
    "driving": "driving", "energetic": "driving", "sport": "driving", "rock": "driving",
    "trap": "driving", "phonk": "driving",
    "chill": "chill", "calm": "chill", "lofi": "chill", "ambient": "chill",
    "acoustic": "chill", "soft": "chill", "emotional": "chill",
    "cinematic": "cinematic", "trailer": "cinematic", "dramatic": "cinematic",
    "epic": "cinematic",
}


def mood_of(name: str) -> str | None:
    """Infer a canonical mood from filename tokens (None if nothing matches)."""
    low = Path(name).stem.lower().replace("-", "_")
    for tok in low.split("_"):
        if tok in MOOD_TOKENS:
            return MOOD_TOKENS[tok]
    for tok, mood in MOOD_TOKENS.items():   # substring fallback ("chillwave-mix.mp3")
        if tok in low:
            return mood
    return None


def _licensed_dirs(cfg: Config) -> list[Path]:
    dirs = []
    conf = cfg.data.get("music", {}).get("licensed_dir")
    if conf:
        p = Path(conf)
        dirs.append(p if p.is_absolute() else cfg.root / p)
    dirs.append(cfg.root / "assets" / "music" / "licensed")
    seen, out = set(), []
    for d in dirs:
        if d not in seen:
            seen.add(d); out.append(d)
    return out


def scan_music(cfg: Config, *, force: bool = False) -> list[dict]:
    """Index licensed tracks: path, duration, BPM (detected), mood (filename). Cached by mtime."""
    from ..media.ffprobe import probe
    from ..analysis.beats import estimate_tempo

    cache_file = cfg.cache_dir / "music_meta.json"
    cache = {}
    if cache_file.exists() and not force:
        try:
            cache = json.loads(cache_file.read_text())
        except Exception:
            cache = {}

    tracks = []
    for d in _licensed_dirs(cfg):
        if not d.exists():
            continue
        for f in sorted(d.rglob("*")):
            if f.suffix.lower() not in AUDIO_EXTS or not f.is_file():
                continue
            key = str(f)
            mtime = f.stat().st_mtime
            meta = cache.get(key)
            if not meta or meta.get("mtime") != mtime:
                try:
                    dur = probe(f).duration
                except Exception:
                    continue
                bpm = estimate_tempo(f)
                meta = {"mtime": mtime, "duration": round(dur or 0.0, 2), "bpm": bpm}
                cache[key] = meta
            tracks.append({"path": key, "name": f.name, "duration": meta["duration"],
                           "bpm": meta["bpm"], "mood": mood_of(f.name), "licensed": True})
    cfg.cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(cache, indent=1))
    return tracks


def pick_from(tracks: list[dict], *, mood: str | None = None,
              min_duration: float | None = None) -> dict | None:
    """Pure picker: exact-mood matches first (then unmoded), longest-first within a tier."""
    ok = [t for t in tracks if not min_duration or (t.get("duration") or 0) >= min_duration]
    if not ok:
        return None
    if mood:
        exact = [t for t in ok if t.get("mood") == mood]
        untagged = [t for t in ok if t.get("mood") is None]
        pool = exact or untagged or ok
    else:
        pool = ok
    return sorted(pool, key=lambda t: -(t.get("duration") or 0))[0]


def pick_music(cfg: Config, *, mood: str | None = None,
               min_duration: float | None = None) -> dict:
    """Best licensed track for the brief; procedural bed fallback (never returns None)."""
    choice = pick_from(scan_music(cfg), mood=mood, min_duration=min_duration)
    if choice:
        return choice
    from ..render.music_gen import ensure_beds, STYLES
    style = mood if mood in ("upbeat", "driving", "chill") else "driving"
    beds = ensure_beds(cfg.root / "assets" / "music")
    return {"path": str(beds[style]), "name": f"bed_{style}.wav",
            "duration": 24.0, "bpm": float(STYLES[style]["bpm"]),
            "mood": style, "licensed": False}
