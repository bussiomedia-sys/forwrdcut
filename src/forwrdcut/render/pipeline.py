"""Render core: trim → reframe to 9:16 → burn caption → HW encode.

`render_slice` is the public single-segment entry (writes a reproducible
`.edp.json` sidecar). `render_segment` renders a concat-safe normalized segment
used by the multi-segment timeline assembler (see render/timeline.py).
"""
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from ..config import Config, load_config
from ..media.ffmpeg import fmt_time, pick_video_encoder, run
from ..media.ffprobe import probe
from .caption_video import build_caption_frames
from .captions import render_caption_png
from .grade import grade_chain
from .reframe import reframe_chain, tracked_chain


def _motion_chain(motion: str | None, w: int, h: int, fps: int,
                  pulses: list[float] | None = None) -> str:
    """Leading-comma filter for a per-segment camera move on the WxH base.
    Pre-scales 2x then zoompan-samples back so the move stays sharp + smooth.
    Captions overlay AFTER this, so text never moves — only the footage does.

    ``motion`` adds a slow drift (zoom_in/zoom_out/punch). ``pulses`` is a list of
    times (seconds from segment start) to add a quick emphasis scale-pop on — this is
    the 'punch on the important word' beat that makes a modern edit feel alive. The two
    compose: a slow push plus snappy accents."""
    # absolute, frame-indexed drift (on = output frame number at `fps`)
    drift = {
        "zoom_in":  "min(0.00060*on,0.10)",
        "zoom_out": "max(0.10-0.00060*on,0.0)",
        "punch":    "min(0.00300*on,0.08)",
    }
    base = drift.get(motion or "", None)
    if base is None and not pulses:
        return ""
    parts = ["1.0"]
    if base is not None:
        parts.append(f"({base})")
    if pulses:
        width = max(1.0, 0.10 * fps)          # ~100ms pop
        amp = 0.060                            # 6% scale punch
        bumps = "+".join(
            f"{amp}*exp(-pow((on-{t * fps:.1f})/{width:.1f}\\,2))" for t in pulses if t >= 0)
        if bumps:
            parts.append(f"({bumps})")
    z = "min(" + "+".join(parts) + ",1.22)"
    return (f",scale={w * 2}:{h * 2}:flags=bicubic,"
            f"zoompan=z='{z}':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"s={w}x{h}:fps={fps}")


def _build_caption_track(cfg, dur, tw, th, target_fps, words, caption_text, position, style):
    """Returns (extra_inputs, overlay_input_label_present, caption_kind, tmpdir)."""
    ccfg = cfg.captions
    font = ccfg.get("font")
    if font and font != "auto" and not Path(font).is_absolute():
        font = str(cfg.root / font)          # resolve Inter path relative to project root
    safe = dict(
        safe_top_frac=float(ccfg.get("safe_top_frac", 0.13)),
        safe_bottom_frac=float(ccfg.get("safe_bottom_frac", 0.24)),
        safe_side_frac=float(ccfg.get("safe_side_frac", 0.08)),
    )
    if words:
        tmpdir = Path(tempfile.mkdtemp(prefix="forwrdcut_"))
        build_caption_frames(
            words, dur, target_fps, (tw, th), tmpdir, style=style,
            font_path=font, fill=ccfg.get("fill", "#FFFFFF"),
            stroke=ccfg.get("stroke", "#000000"), highlight=ccfg.get("highlight", "#EA6024"),
            position=position, **safe,
        )
        return (["-framerate", str(target_fps), "-i", str(tmpdir / "cap_%05d.png")],
                True, "animated", tmpdir)
    if caption_text:
        tmpdir = Path(tempfile.mkdtemp(prefix="forwrdcut_"))
        png = tmpdir / "caption.png"
        render_caption_png(
            caption_text, png, frame_size=(tw, th), style=style,
            font_path=font, fill=ccfg.get("fill", "#FFFFFF"),
            stroke=ccfg.get("stroke", "#000000"), position=position, **safe,
        )
        return (["-loop", "1", "-t", fmt_time(dur), "-i", str(png)], True, "static", tmpdir)
    return ([], False, "none", None)


def _render_core(clip_path, start, end, out_path, *, cfg, tw, th, target_fps,
                 words=None, caption_text=None, position="lower", reframe_mode=None,
                 caption_style=None, mute_audio=False, motion=None, emphasis_times=None,
                 faststart=True) -> dict:
    clip_path = Path(clip_path)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    info = probe(clip_path)
    start = max(0.0, float(start))
    end = min(float(end), info.duration) if info.duration else float(end)
    dur = max(0.05, end - start)

    rcfg = cfg.render
    mode = reframe_mode or rcfg.get("reframe_mode", "cover")
    if mode == "smart":
        from ..analysis.reframe_track import compute_crop_plan
        plan = compute_crop_plan(cfg, clip_path, start, end, tw, th)
        chain = tracked_chain(plan) if plan else reframe_chain(tw, th, "cover")
    else:
        chain = reframe_chain(tw, th, mode)
    motion_fc = _motion_chain(motion, tw, th, target_fps, pulses=emphasis_times)
    g = grade_chain(cfg)
    gc = f",{g}" if g else ""
    base_chain = f"[0:v]{chain}{gc},fps={target_fps}{motion_fc}[base]"

    style = caption_style or cfg.captions.get("style", "bold-pop")
    inputs = ["-ss", fmt_time(start), "-t", fmt_time(dur), "-i", str(clip_path)]
    extra, has_overlay, caption_kind, tmpdir = _build_caption_track(
        cfg, dur, tw, th, target_fps, words, caption_text, position, style)
    inputs += extra

    if has_overlay:
        fc = f"{base_chain};[base][1:v]overlay=0:0:shortest=1,format=yuv420p[vout]"
    else:
        fc = f"[0:v]{chain}{gc},fps={target_fps}{motion_fc},format=yuv420p[vout]"

    # Always emit a stereo 48k audio track (silent if the source has none) so
    # segments are concat-compatible. Map only the FIRST audio stream — iPhone
    # MOVs carry phantom audio/metadata tracks (codec "none") that break -map 0:a?.
    if info.has_audio and not mute_audio:
        audio_map = "0:a:0?"
    else:
        inputs += ["-f", "lavfi", "-t", fmt_time(dur),
                   "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
        audio_map = f"{len([x for x in inputs if x == '-i'])-1}:a"

    venc = pick_video_encoder(rcfg.get("hw_encoder", "h264_videotoolbox"),
                              rcfg.get("sw_encoder", "libx264"))
    args = [
        *inputs,
        "-filter_complex", fc,
        "-map", "[vout]", "-map", audio_map,
        "-c:v", venc, "-b:v", str(rcfg.get("video_bitrate", "10M")),
        "-pix_fmt", "yuv420p", "-r", str(target_fps),
        "-c:a", "aac", "-b:a", str(rcfg.get("audio_bitrate", "192k")),
        "-ar", "48000", "-ac", "2", "-dn", "-ignore_unknown",
    ]
    if faststart:
        args += ["-movflags", "+faststart"]
    args += [str(out_path)]

    run(args, desc=f"render -> {out_path.name}")
    return {"caption_kind": caption_kind, "in": round(start, 3), "out": round(end, 3),
            "duration": round(dur, 3), "encoder": venc, "args": args}


def render_segment(clip_path, start, end, out_path, *, cfg, tw, th, target_fps,
                   words=None, caption_text=None, position="center", reframe_mode=None,
                   caption_style=None, mute_audio=False, motion=None, emphasis_times=None) -> dict:
    """Render one normalized, concat-safe segment (no sidecar, no faststart)."""
    return _render_core(clip_path, start, end, out_path, cfg=cfg, tw=tw, th=th,
                        target_fps=target_fps, words=words, caption_text=caption_text,
                        position=position, reframe_mode=reframe_mode,
                        caption_style=caption_style, mute_audio=mute_audio, motion=motion,
                        emphasis_times=emphasis_times, faststart=False)


def render_vo_segment(clip_path, start, vo_wav, words, out_path, *, cfg, tw, th,
                      target_fps, position="center", caption_style=None,
                      reframe_mode=None, motion=None) -> dict:
    """Render a voiceover-driven segment: duration = VO length, captions word-synced
    to the VO, source muted, video freezes on its last frame if shorter than the VO."""
    clip_path, out_path, vo_wav = Path(clip_path), Path(out_path), Path(vo_wav)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    info = probe(clip_path)
    dur = probe(vo_wav).duration

    rcfg = cfg.render
    mode = reframe_mode or rcfg.get("reframe_mode", "cover")
    if mode == "smart":
        from ..analysis.reframe_track import compute_crop_plan
        plan = compute_crop_plan(cfg, clip_path, start, min(start + dur, info.duration), tw, th)
        chain = tracked_chain(plan) if plan else reframe_chain(tw, th, "cover")
    else:
        chain = reframe_chain(tw, th, mode)
    style = caption_style or cfg.captions.get("style", "bold-pop")

    # video: read from `start`, slightly past the VO; tpad clones the last frame to
    # fill any gap; output is capped to the VO duration.
    inputs = ["-ss", fmt_time(start), "-t", fmt_time(dur + 0.5), "-i", str(clip_path)]
    extra, has_overlay, _, _ = _build_caption_track(
        cfg, dur, tw, th, target_fps, words, None, position, style)
    inputs += extra
    inputs += ["-i", str(vo_wav)]
    vo_idx = sum(1 for x in inputs if x == "-i") - 1

    motion_fc = _motion_chain(motion, tw, th, target_fps)
    g = grade_chain(cfg)
    gc = f",{g}" if g else ""
    held = f"[0:v]{chain}{gc},fps={target_fps},tpad=stop_mode=clone:stop_duration={dur:.3f}{motion_fc}"
    if has_overlay:
        fc = f"{held}[base];[base][1:v]overlay=0:0:shortest=1,format=yuv420p[vout]"
    else:
        fc = f"{held},format=yuv420p[vout]"

    venc = pick_video_encoder(rcfg.get("hw_encoder", "h264_videotoolbox"),
                              rcfg.get("sw_encoder", "libx264"))
    args = [
        *inputs, "-filter_complex", fc, "-map", "[vout]", "-map", f"{vo_idx}:a",
        "-c:v", venc, "-b:v", str(rcfg.get("video_bitrate", "10M")),
        "-pix_fmt", "yuv420p", "-r", str(target_fps),
        "-c:a", "aac", "-b:a", str(rcfg.get("audio_bitrate", "192k")), "-ar", "48000", "-ac", "2",
        "-t", f"{dur:.3f}", "-dn", "-ignore_unknown", str(out_path),
    ]
    run(args, desc=f"vo segment -> {out_path.name}")
    return {"duration": round(dur, 3)}


def render_slice(
    clip_path: str | Path,
    start: float,
    end: float,
    caption_text: str | None,
    out_path: str | Path,
    *,
    cfg: Config | None = None,
    preview: bool = False,
    position: str = "lower",
    reframe_mode: str | None = None,
    words: list[dict] | None = None,
    caption_style: str | None = None,
) -> dict:
    cfg = cfg or load_config()
    out_path = Path(out_path)
    rcfg = cfg.render
    info = probe(clip_path)
    if preview:
        tw, th = int(rcfg.get("preview_width", 540)), int(rcfg.get("preview_height", 960))
    else:
        tw, th = int(rcfg.get("target_width", 1080)), int(rcfg.get("target_height", 1920))
    target_fps = int(rcfg.get("fps") or 0) or int(round(info.fps)) or 30

    core = _render_core(clip_path, start, end, out_path, cfg=cfg, tw=tw, th=th,
                        target_fps=target_fps, words=words, caption_text=caption_text,
                        position=position, reframe_mode=reframe_mode,
                        caption_style=caption_style, faststart=True)

    edp = {
        "source": str(clip_path), "in": core["in"], "out": core["out"],
        "duration": core["duration"], "fps": target_fps,
        "caption_kind": core["caption_kind"], "caption": caption_text,
        "words": words if core["caption_kind"] == "animated" else None,
        "caption_position": position, "reframe_mode": reframe_mode or rcfg.get("reframe_mode", "cover"),
        "target": [tw, th], "video_encoder": core["encoder"], "preview": preview,
        "output": str(out_path), "ffmpeg_args": core["args"],
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    sidecar = out_path.with_suffix(out_path.suffix + ".edp.json")
    sidecar.write_text(json.dumps(edp, indent=2))

    out_info = probe(out_path)
    return {
        "output": str(out_path), "sidecar": str(sidecar),
        "size_bytes": out_info.size_bytes, "duration": out_info.duration,
        "resolution": f"{out_info.width}x{out_info.height}", "encoder": core["encoder"],
    }
