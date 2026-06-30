"""Annotate an existing video with timed, fading text overlays — for landing-page
hero loops. Keeps the source's native aspect/resolution, drops audio, applies no
reframe/crop/grade (preserves product color). Each callout fades in/out.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from ..config import Config, load_config
from ..media.ffmpeg import pick_video_encoder, run
from ..media.ffprobe import probe
from .graphics import feature_callout
from .reframe import cover_chain


def annotate_hero(src: str | Path, out: str | Path, callouts: list[dict], *,
                  cfg: Config | None = None, fade: float = 0.35, fps: int = 30,
                  bitrate: str = "12M", position: str = "lower-left",
                  out_size: tuple[int, int] | None = None) -> dict:
    """callouts: [{"text", "start", "end", "position"(opt), "subtext"(opt)}].
    out_size scales/center-crops to (w,h) — e.g. (1920,1080) or (1080,1080)."""
    cfg = cfg or load_config()
    src, out = Path(src), Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    info = probe(src)
    fw, fh, total = info.width, info.height, info.duration
    ow, oh = out_size or (fw, fh)

    tmp = Path(tempfile.mkdtemp(prefix="forwrdcut_hero_"))
    items = []
    for i, c in enumerate(callouts):
        img = feature_callout(c["text"], (ow, oh), cfg,
                              position=c.get("position", position),
                              subtext=c.get("subtext"))
        p = tmp / f"c{i}.png"
        img.save(p)
        items.append((p, float(c["start"]), float(c["end"])))

    inputs = ["-i", str(src)]
    for p, _, _ in items:
        inputs += ["-loop", "1", "-t", f"{total:.3f}", "-i", str(p)]

    if (ow, oh) != (fw, fh):
        chain, lab = [f"[0:v]{cover_chain(ow, oh)}[bg]"], "bg"
    else:
        chain, lab = [], "0:v"
    for i, (p, s, e) in enumerate(items, start=1):
        fo = max(s, e - fade)
        chain.append(
            f"[{i}:v]format=rgba,fade=t=in:st={s:.2f}:d={fade}:alpha=1,"
            f"fade=t=out:st={fo:.2f}:d={fade}:alpha=1[c{i}]")
        chain.append(f"[{lab}][c{i}]overlay=0:0:enable='between(t,{s:.2f},{e:.2f})'[v{i}]")
        lab = f"v{i}"

    venc = pick_video_encoder(cfg.render.get("hw_encoder", "h264_videotoolbox"),
                              cfg.render.get("sw_encoder", "libx264"))
    args = [*inputs, "-filter_complex", ";".join(chain), "-map", f"[{lab}]",
            "-c:v", venc, "-b:v", bitrate, "-pix_fmt", "yuv420p", "-r", str(fps),
            "-an", "-movflags", "+faststart", str(out)]
    run(args, desc=f"annotate hero -> {out.name}")
    o = probe(out)
    return {"output": str(out), "resolution": f"{o.width}x{o.height}",
            "duration": round(o.duration, 2), "size_kb": o.size_bytes // 1024}
