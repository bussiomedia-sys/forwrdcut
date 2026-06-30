"""FORWRDCUT MCP server — exposes the editing engine as agent-callable tools.

Run (stdio):  forwrdcut-mcp     (or: python -m forwrdcut.mcp.server)

Register with Claude Code:
    claude mcp add forwrdcut -- /ABS/PATH/.venv/bin/forwrdcut-mcp

Design: the engine is deterministic; the *agent* is the brain. Trend grounding is
agent-driven — research current formats with web search, then pass a `trends`
dict to generate_plan/auto to ground the strategy. If ANTHROPIC_API_KEY is set,
generate_plan additionally polishes the hook with Claude.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

from ..config import load_config
from ..media.ffprobe import probe

mcp = FastMCP("forwrdcut")


def _cfg():
    return load_config()


# ---- library ---------------------------------------------------------------
@mcp.tool()
def scan_library() -> list[dict]:
    """Index every video in the source folder (read-only). Returns clip summaries."""
    from ..analysis.scan import scan_library as _scan
    return [c.to_dict() for c in _scan(_cfg())]


@mcp.tool()
def list_clips() -> list[dict]:
    """List clips already present in the library index (no re-scan)."""
    from .. import project
    cfg = _cfg()
    con = project.connect(cfg.db_path)
    try:
        return project.all_clips(con)
    finally:
        con.close()


@mcp.tool()
def get_clip_info(path: str) -> dict:
    """Probe one clip: duration, resolution, fps, codecs, orientation, rotation."""
    return probe(path).to_dict()


# ---- analysis --------------------------------------------------------------
@mcp.tool()
def analyze_clip(path: str, force: bool = False) -> dict:
    """Full analysis (cached): scene cuts + audio (silence/loudness) + word-level
    transcript + ranked hook lines and highlight windows."""
    from ..analysis.scoring import analyze_clip as _an
    a = _an(_cfg(), path, force=force)
    return {
        "filename": a["filename"], "duration": a["duration"],
        "orientation": a["orientation"], "resolution": a["resolution"],
        "has_audio": a["has_audio"], "n_scenes": a["n_scenes"],
        "hooks": a["hooks"][:8], "highlights": a["highlights"][:8],
        "scenes": a["scenes"], "transcript_text": a["transcript_text"],
    }


@mcp.tool()
def transcribe(path: str) -> dict:
    """Word-level transcript (cached). Use for caption sync and finding hook lines."""
    from ..analysis.transcribe import transcribe_cached
    t = transcribe_cached(_cfg(), path)
    return {"language": t["language"], "full_text": t["full_text"],
            "n_words": len(t["words"]), "words": t["words"]}


# ---- trends ----------------------------------------------------------------
@mcp.tool()
def save_trends(platform: str, niche: str, trends: dict) -> dict:
    """Persist agent-researched trend data so plans are grounded in *now*. Suggested
    keys: length_target (s), caption_style, hook_formats[], sounds[], hashtags[],
    goal, notes. The agent should research these with web search before calling."""
    from ..strategy.trends import save_trends as _save
    return {"saved": str(_save(_cfg(), platform, niche, trends))}


@mcp.tool()
def get_trends(platform: str, niche: str) -> Optional[dict]:
    """Load the cached trends file for a platform+niche (None if absent)."""
    from ..strategy.trends import load_trends
    return load_trends(_cfg(), platform, niche)


# ---- strategy --------------------------------------------------------------
@mcp.tool()
def generate_plan(clip: str, platform: str = "tiktok", seconds: Optional[float] = None,
                  trends: Optional[dict] = None, refine: bool = True) -> dict:
    """Generate an Edit Decision Plan (hook + payoff segments) from analysis.
    Grounds in cached trends for the niche if `trends` is not supplied; pass an
    explicit `trends` dict to override. Saves the plan JSON and returns it."""
    from ..strategy.planner import plan_clip
    from ..strategy import edp as edpmod
    cfg = _cfg()
    if trends is None:
        from ..strategy.trends import load_trends
        trends = load_trends(cfg, platform, cfg.brand.get("niche", ""))
    edp = plan_clip(cfg, clip, platform=platform, target_seconds=seconds,
                    trends=trends, refine=refine)
    out = cfg.output_dir / f"{edp['project']}.edp.json"
    edpmod.save(edp, out)
    return {"plan_path": str(out), "pretty": edpmod.pretty(edp), "plan": edp}


@mcp.tool()
def get_plan(plan_path: str) -> dict:
    """Load a saved Edit Decision Plan JSON."""
    from ..strategy import edp as edpmod
    return edpmod.load(plan_path)


@mcp.tool()
def edit_plan(plan_path: str, updates: dict) -> dict:
    """Apply top-level updates to a saved plan (e.g. swap hook text, reorder/replace
    segments, change captions) and save. Returns the new pretty view + validation."""
    from ..strategy import edp as edpmod
    edp = edpmod.load(plan_path)
    edp.update(updates)
    edpmod.save(edp, plan_path)
    return {"plan_path": plan_path, "pretty": edpmod.pretty(edp),
            "errors": edpmod.validate(edp)}


# ---- render ----------------------------------------------------------------
@mcp.tool()
def render_plan(plan_path: str, preview: bool = False) -> dict:
    """Render a (possibly hand-edited) Edit Decision Plan to a finished 9:16 video."""
    from ..render.timeline import render_timeline
    from ..strategy import edp as edpmod
    cfg = _cfg()
    edp = edpmod.load(plan_path)
    errs = edpmod.validate(edp)
    if errs:
        return {"ok": False, "errors": errs}
    out = ((cfg.preview_dir if preview else cfg.output_dir)
           / f"{edp.get('project', 'plan')}_9x16{'_preview' if preview else ''}.mp4")
    return {"ok": True, **render_timeline(edp, out, cfg, preview=preview)}


@mcp.tool()
def render_preview(plan_path: str) -> dict:
    """Fast low-res preview render of a plan (540x960)."""
    return render_plan(plan_path, preview=True)


@mcp.tool()
def auto(clip: str, platform: str = "tiktok", seconds: Optional[float] = None,
         trends: Optional[dict] = None, preview: bool = False) -> dict:
    """One shot: analyze → plan → multi-segment captioned render → concat.
    Returns the plan and the render result."""
    from ..strategy.planner import plan_clip
    from ..strategy import edp as edpmod
    from ..render.timeline import render_timeline
    cfg = _cfg()
    if trends is None:
        from ..strategy.trends import load_trends
        trends = load_trends(cfg, platform, cfg.brand.get("niche", ""))
    edp = plan_clip(cfg, clip, platform=platform, target_seconds=seconds, trends=trends)
    out = ((cfg.preview_dir if preview else cfg.output_dir)
           / f"{edp['project']}_9x16{'_preview' if preview else ''}.mp4")
    res = render_timeline(edp, out, cfg, preview=preview)
    return {"pretty": edpmod.pretty(edp), "plan": edp, **res}


@mcp.tool()
def batch(platform: str = "tiktok", n: int = 3, trends: Optional[dict] = None,
          seconds: Optional[float] = None, clips: Optional[list] = None,
          preview: bool = False) -> dict:
    """Make N finished clips from the library: rank clips by viral potential, then
    plan + render each (trend-grounded). Pads with variants of the top clip if the
    library has fewer than N usable clips."""
    from ..strategy.batch import make_batch
    from ..render.timeline import render_timeline
    cfg = _cfg()
    if trends is None:
        from ..strategy.trends import load_trends
        trends = load_trends(cfg, platform, cfg.brand.get("niche", ""))
    plans = make_batch(cfg, platform=platform, n=n, trends=trends, seconds=seconds, clips=clips)
    results = []
    for edp in plans:
        out = ((cfg.preview_dir if preview else cfg.output_dir)
               / f"{edp['project']}_9x16{'_preview' if preview else ''}.mp4")
        res = render_timeline(edp, out, cfg, preview=preview)
        results.append({"project": edp["project"], "hook": edp["hook"]["text"], **res})
    return {"count": len(results), "clips": results}


@mcp.tool()
def render_slice(clip: str, start: float, end: float, text: Optional[str] = None,
                 auto_captions: bool = False, preview: bool = False,
                 position: str = "center") -> dict:
    """Render one trimmed 9:16 slice with optional static `text` or `auto_captions`
    (word-synced from the speech in range)."""
    from ..render.pipeline import render_slice as _rs
    from ..analysis.transcribe import transcribe_cached, words_in_range
    cfg = _cfg()
    words = None
    if auto_captions:
        words = words_in_range(transcribe_cached(cfg, clip)["words"], start, end)
    out = ((cfg.preview_dir if preview else cfg.output_dir)
           / f"{Path(clip).stem}_slice_9x16{'_preview' if preview else ''}.mp4")
    return _rs(clip, start, end, text, out, words=words, cfg=cfg,
               preview=preview, position=position)


@mcp.tool()
def list_outputs() -> list[dict]:
    """List rendered outputs in the output folder."""
    cfg = _cfg()
    outs = []
    for p in sorted(cfg.output_dir.glob("*.mp4")):
        try:
            i = probe(p)
            outs.append({"path": str(p), "duration": i.duration,
                         "resolution": f"{i.width}x{i.height}", "size_bytes": i.size_bytes})
        except Exception:
            pass
    return outs


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
