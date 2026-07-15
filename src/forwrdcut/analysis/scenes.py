"""Shot / scene boundary detection via PySceneDetect.

Produces a list of cuttable segments with timestamps — raw material for pacing,
re-hooks, and b-roll selection. Cached by file hash.

Scene detection runs in an isolated subprocess: PySceneDetect pulls in OpenCV,
which bundles its own libav. faster-whisper pulls in PyAV, which bundles another.
Loading both in one process triggers an "AVFFrameReceiver implemented in both…"
objc clash (and risks crashes). Running scenedetect in a child process keeps
OpenCV out of the main interpreter entirely.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from ..config import Config
from ..media.ffprobe import probe
from .. import project

_WORKER = r"""
import json, sys
from scenedetect import detect, ContentDetector
path, thr, msl = sys.argv[1], float(sys.argv[2]), int(float(sys.argv[3]) * 30)
sl = detect(path, ContentDetector(threshold=thr, min_scene_len=msl))
out = [{
    "index": i,
    "start": round(s.get_seconds(), 3),
    "end": round(e.get_seconds(), 3),
    "duration": round(e.get_seconds() - s.get_seconds(), 3),
} for i, (s, e) in enumerate(sl)]
print(json.dumps(out))
"""


def detect_scenes(path: str | Path, *, threshold: float = 27.0,
                  min_scene_len: float = 0.6) -> list[dict]:
    proc = subprocess.run(
        [sys.executable, "-c", _WORKER, str(path), str(threshold), str(min_scene_len)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"scene detection failed for {path}:\n{proc.stderr[-1500:]}")
    line = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else "[]"
    return json.loads(line)


def detect_scenes_cached(cfg: Config, path: str | Path, *, force: bool = False) -> list[dict]:
    path = Path(path)
    info = probe(path)
    con = project.connect(cfg.db_path)
    try:
        if not force:
            cached = project.get_analysis(con, str(path), "scenes", info.file_hash)
            if cached is not None:
                return cached.get("scenes", [])
        scenes = detect_scenes(path)
        project.save_analysis(con, str(path), "scenes", info.file_hash, {"scenes": scenes})
        return scenes
    finally:
        con.close()
