"""Optional Claude refinement layer for Edit Decision Plans.

This is the *pluggable* half of the agent-driven brain: the rule-based planner
always runs; if (and only if) an ANTHROPIC_API_KEY is present, this module asks
Claude to sharpen the hook copy and propose a bold overlay line, grounded in the
transcript and any trend data the agent supplied. With no key it is never called.
"""
from __future__ import annotations

import json
import os
import re

from ..config import Config

_DEFAULT_MODEL = "claude-opus-4-8"


def available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def refine_plan(cfg: Config, edp: dict, analysis: dict) -> dict:
    from anthropic import Anthropic

    client = Anthropic()
    model = cfg.data.get("strategy", {}).get("model") or _DEFAULT_MODEL
    transcript = (analysis.get("transcript_text") or "")[:3000]
    trends = edp.get("trends") or {}
    niche = cfg.brand.get("niche", "")

    prompt = (
        "You are a world-class short-form social video editor. Given a transcript and a draft "
        "edit plan, write the single most arresting 1–3 second HOOK (open loop / curiosity gap / "
        "pattern interrupt) and a short bold OVERLAY line for the first ~2s. Keep them punchy and "
        "platform-native; do not fabricate facts not supported by the transcript.\n\n"
        f"Platform: {edp.get('platform')}\nNiche: {niche}\n"
        f"Trends (may be empty): {json.dumps(trends)[:800]}\n"
        f"Current hook: {edp.get('hook', {}).get('text', '')}\n\n"
        f"Transcript:\n{transcript}\n\n"
        'Reply with ONLY JSON: {"hook_text": "...", "overlay_text": "...", "why": "..."}'
    )
    msg = client.messages.create(
        model=model, max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(getattr(b, "text", "") for b in msg.content)
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return edp
    data = json.loads(m.group(0))

    if data.get("hook_text"):
        edp["hook"]["text"] = data["hook_text"]
        edp["hook"]["type"] = "spoken+overlay"
        edp["hook"]["why"] = data.get("why", edp["hook"].get("why", ""))
    if data.get("overlay_text") and edp.get("segments"):
        # Persistent bold hook overlay over the first segment.
        edp["segments"][0]["caption"] = {"text": data["overlay_text"]}
    edp["notes"] = (edp.get("notes", "") + "  (hook refined by Claude)").strip()
    return edp
