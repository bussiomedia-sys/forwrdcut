"""Trend cache — grounding strategy in what's winning *now*.

The brain is agent-driven: a Claude Code agent researches current short-form
patterns (hook formats, length windows, caption styles, sound/hashtag notes) with
web search, then persists a timestamped trends file here via `save_trends` (or the
MCP tool). The planner auto-loads the freshest matching file so plans reflect now,
not training-data priors. Stale files (older than max_age_days) are ignored.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from ..config import Config


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "general").lower()).strip("-") or "general"


def save_trends(cfg: Config, platform: str, niche: str, data: dict) -> Path:
    d = cfg.path("trends_dir")
    d.mkdir(parents=True, exist_ok=True)
    payload = {"platform": platform, "niche": niche, "fetched_at": _now(), **data}
    out = d / f"{platform}_{_slug(niche)}.json"
    out.write_text(json.dumps(payload, indent=2))
    return out


def load_trends(cfg: Config, platform: str, niche: str,
                *, max_age_days: int = 14) -> dict | None:
    path = cfg.path("trends_dir") / f"{platform}_{_slug(niche)}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    try:
        fetched = datetime.fromisoformat(data.get("fetched_at"))
        age = (datetime.now(timezone.utc) - fetched).days
        if age > max_age_days:
            data["_stale"] = True
    except Exception:
        pass
    return data
