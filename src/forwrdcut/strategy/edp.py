"""Edit Decision Plan (EDP) — the reviewable, reproducible edit document.

An EDP is plain JSON so the agent (or a human) can read and edit it before
rendering. It is the single input to the timeline assembler.

Shape::

    {
      "version": 1,
      "project": "ranger_tiktok",
      "platform": "tiktok",
      "goal": "...",
      "target": {"width": 1080, "height": 1920, "fps": 30},
      "hook": {"type": "spoken|overlay|visual", "text": "...", "why": "..."},
      "captions": {"mode": "auto", "style": "bold-pop", "position": "center"},
      "segments": [
        {"source": "...", "in": 0.0, "out": 5.0, "role": "hook",
         "reframe": "cover", "caption": "auto" | "none" | {"text": "..."}}
      ],
      "sfx": [{"name": "whoosh", "at": 5.0}],     # cue points (slots for now)
      "music": {"slot": true, "note": "add trending sound in-app"},
      "trends": { ... optional grounding the agent supplied ... },
      "notes": "..."
    }
"""
from __future__ import annotations

import json
from pathlib import Path


def total_duration(edp: dict) -> float:
    return round(sum(max(0.0, s["out"] - s["in"]) for s in edp.get("segments", [])), 2)


def validate(edp: dict) -> list[str]:
    errs: list[str] = []
    if not edp.get("segments"):
        errs.append("EDP has no segments")
    for i, s in enumerate(edp.get("segments", [])):
        if not s.get("source"):
            errs.append(f"segment {i}: missing source")
        if not Path(s["source"]).exists() if s.get("source") else True:
            if s.get("source"):
                errs.append(f"segment {i}: source not found: {s['source']}")
        if s.get("out", 0) <= s.get("in", 0):
            errs.append(f"segment {i}: out must be > in")
    return errs


def save(edp: dict, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(edp, indent=2))
    return path


def load(path: str | Path) -> dict:
    return json.loads(Path(path).read_text())


def pretty(edp: dict) -> str:
    lines = []
    lines.append(f"Project : {edp.get('project','(unnamed)')}   Platform: {edp.get('platform')}")
    if edp.get("goal"):
        lines.append(f"Goal    : {edp['goal']}")
    hook = edp.get("hook") or {}
    if hook:
        lines.append(f"Hook    : [{hook.get('type')}] {hook.get('text','')}")
        if hook.get("why"):
            lines.append(f"          ↳ {hook['why']}")
    caps = edp.get("captions", {})
    lines.append(f"Captions: {caps.get('mode')} / {caps.get('style')} @ {caps.get('position')}")
    lines.append(f"Length  : {total_duration(edp):.1f}s across {len(edp.get('segments', []))} segment(s)")
    lines.append("Segments:")
    for i, s in enumerate(edp.get("segments", [])):
        cap = s.get("caption")
        cap_s = cap if isinstance(cap, str) else f"text:{cap.get('text','')!r}"
        lines.append(f"  {i+1}. [{s.get('role','seg'):>6}] {Path(s['source']).name}  "
                     f"{s['in']:.1f}-{s['out']:.1f}s  ({s['out']-s['in']:.1f}s)  cap={cap_s}")
    if edp.get("sfx"):
        lines.append("SFX cues: " + ", ".join(f"{c['name']}@{c['at']:.1f}s" for c in edp["sfx"]))
    if edp.get("music", {}).get("slot"):
        lines.append(f"Music   : [slot] {edp['music'].get('note','')}")
    return "\n".join(lines)
