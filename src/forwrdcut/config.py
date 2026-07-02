"""Project configuration loader.

Reads ``config.toml`` from the project root and exposes resolved paths and
section dicts. Paths in the TOML are resolved relative to the config file's
directory so the project is relocatable.
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

# src/forwrdcut/config.py -> parents[2] is the project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Config:
    root: Path
    data: dict

    def path(self, key: str) -> Path:
        rel = Path(self.data["paths"][key])
        return rel if rel.is_absolute() else (self.root / rel)

    @property
    def source_dir(self) -> Path:
        return self.path("source_dir")

    @property
    def output_dir(self) -> Path:
        return self.path("output_dir")

    @property
    def preview_dir(self) -> Path:
        return self.path("preview_dir")

    @property
    def cache_dir(self) -> Path:
        return self.path("cache_dir")

    @property
    def db_path(self) -> Path:
        return self.path("db_path")

    @property
    def brand(self) -> dict:
        return self.data.get("brand", {})

    @property
    def render(self) -> dict:
        return self.data.get("render", {})

    @property
    def captions(self) -> dict:
        return self.data.get("captions", {})

    @property
    def transcription(self) -> dict:
        return self.data.get("transcription", {})

    @property
    def vision(self) -> dict:
        return self.data.get("vision", {})

    def ensure_dirs(self) -> None:
        for p in (self.source_dir, self.output_dir, self.preview_dir, self.cache_dir):
            p.mkdir(parents=True, exist_ok=True)


def find_config(start: Path | None = None) -> Path:
    """Search upward from *start* (or cwd) for config.toml; fall back to PROJECT_ROOT."""
    here = (start or Path.cwd()).resolve()
    for d in [here, *here.parents]:
        candidate = d / "config.toml"
        if candidate.exists():
            return candidate
    fallback = PROJECT_ROOT / "config.toml"
    if fallback.exists():
        return fallback
    raise FileNotFoundError(
        "config.toml not found (searched upward from cwd and the project root). "
        "New here? Run `forwrdcut init` in your project folder, then `forwrdcut doctor`.")


@lru_cache(maxsize=4)
def load_config(path: str | None = None) -> Config:
    cfg_path = Path(path).resolve() if path else find_config()
    with open(cfg_path, "rb") as f:
        data = tomllib.load(f)
    return Config(root=cfg_path.parent, data=data)
