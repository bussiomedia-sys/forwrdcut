"""Library scanner: index every video in the source folder via ffprobe.

Read-only with respect to source files. Results are cached in SQLite keyed by a
cheap content hash, so unchanged files are skipped on rescan.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

from ..config import Config
from ..media.ffprobe import MediaInfo, probe, quick_hash
from .. import project

VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".webm", ".mpg", ".mpeg", ".hevc"}


def iter_videos(source_dir: Path) -> Iterator[Path]:
    if not source_dir.exists():
        return
    for p in sorted(source_dir.rglob("*")):
        if p.name.startswith("."):
            continue
        if p.is_file() and p.suffix.lower() in VIDEO_EXTS:
            yield p


def scan_library(cfg: Config, *, force: bool = False) -> list[MediaInfo]:
    cfg.ensure_dirs()
    con = project.connect(cfg.db_path)
    results: list[MediaInfo] = []
    try:
        for f in iter_videos(cfg.source_dir):
            h = quick_hash(f)
            if not force and not project.needs_scan(con, str(f), h):
                cached = project.get_clip(con, str(f))
                if cached:
                    results.append(MediaInfo(**cached))
                    continue
            try:
                info = probe(f)
            except Exception as e:  # keep scanning the rest of the library
                print(f"  ! skipped {f.name}: {e}")
                continue
            project.upsert_clip(con, info)
            results.append(info)
    finally:
        con.close()
    return results
