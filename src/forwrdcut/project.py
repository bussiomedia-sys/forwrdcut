"""SQLite library index + edit-manifest helpers.

The index caches probe results keyed by path+hash so unchanged files are never
re-probed. Manifests (Edit Decision Plans) are stored as JSON sidecars next to
their renders for reproducibility.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .media.ffprobe import MediaInfo

SCHEMA = """
CREATE TABLE IF NOT EXISTS clips (
    path            TEXT PRIMARY KEY,
    filename        TEXT,
    hash            TEXT,
    duration        REAL,
    width           INTEGER,
    height          INTEGER,
    fps             REAL,
    vcodec          TEXT,
    has_audio       INTEGER,
    orientation     TEXT,
    aspect          REAL,
    info_json       TEXT,
    scanned_at      TEXT
);
CREATE TABLE IF NOT EXISTS analysis (
    path            TEXT,
    kind            TEXT,         -- scenes | transcript | vision | audio | score
    hash            TEXT,
    data_json       TEXT,
    created_at      TEXT,
    PRIMARY KEY (path, kind)
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(db_path: str | Path) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    con.commit()
    return con


def needs_scan(con: sqlite3.Connection, path: str, file_hash: str) -> bool:
    row = con.execute("SELECT hash FROM clips WHERE path = ?", (path,)).fetchone()
    return row is None or row["hash"] != file_hash


def upsert_clip(con: sqlite3.Connection, info: MediaInfo) -> None:
    con.execute(
        """
        INSERT INTO clips (path, filename, hash, duration, width, height, fps,
                           vcodec, has_audio, orientation, aspect, info_json, scanned_at)
        VALUES (:path, :filename, :hash, :duration, :width, :height, :fps,
                :vcodec, :has_audio, :orientation, :aspect, :info_json, :scanned_at)
        ON CONFLICT(path) DO UPDATE SET
            filename=excluded.filename, hash=excluded.hash, duration=excluded.duration,
            width=excluded.width, height=excluded.height, fps=excluded.fps,
            vcodec=excluded.vcodec, has_audio=excluded.has_audio,
            orientation=excluded.orientation, aspect=excluded.aspect,
            info_json=excluded.info_json, scanned_at=excluded.scanned_at
        """,
        {
            "path": info.path, "filename": info.filename, "hash": info.file_hash,
            "duration": info.duration, "width": info.width, "height": info.height,
            "fps": info.fps, "vcodec": info.vcodec, "has_audio": int(info.has_audio),
            "orientation": info.orientation, "aspect": info.aspect_ratio,
            "info_json": json.dumps(info.to_dict()), "scanned_at": _now(),
        },
    )
    con.commit()


def get_clip(con: sqlite3.Connection, path: str) -> dict | None:
    row = con.execute("SELECT info_json FROM clips WHERE path = ?", (path,)).fetchone()
    return json.loads(row["info_json"]) if row else None


def all_clips(con: sqlite3.Connection) -> list[dict]:
    rows = con.execute("SELECT info_json FROM clips ORDER BY filename").fetchall()
    return [json.loads(r["info_json"]) for r in rows]


def save_analysis(con: sqlite3.Connection, path: str, kind: str, file_hash: str, data: dict) -> None:
    con.execute(
        """
        INSERT INTO analysis (path, kind, hash, data_json, created_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(path, kind) DO UPDATE SET
            hash=excluded.hash, data_json=excluded.data_json, created_at=excluded.created_at
        """,
        (path, kind, file_hash, json.dumps(data), _now()),
    )
    con.commit()


def get_analysis(con: sqlite3.Connection, path: str, kind: str, file_hash: str | None = None) -> dict | None:
    row = con.execute(
        "SELECT hash, data_json FROM analysis WHERE path = ? AND kind = ?", (path, kind)
    ).fetchone()
    if not row:
        return None
    if file_hash is not None and row["hash"] != file_hash:
        return None  # stale
    return json.loads(row["data_json"])
