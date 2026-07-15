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


_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".heic", ".gif"}


# Every segment must leave the encoder byte-compatible with every other segment, because
# the timeline concatenates them with `-c copy`. JPEG stills decode as full-range
# (`color_range=pc`); `format=yuv420p` alone does NOT reset that flag, so the encoder tags
# the segment `yuvj420p` while video-sourced segments stay `yuv420p`. Mixing the two in a
# copy-concat silently drops beats. The explicit range conversion is what makes them match.
_NORMALIZE = "format=yuv420p,scale=in_range=auto:out_range=tv"


def _is_image(path) -> bool:
    """A still-image source (slideshow slot) vs a video clip."""
    return Path(path).suffix.lower() in _IMAGE_EXTS


def _motion_chain(motion: str | None, w: int, h: int, fps: int,
                  pulses: list[float] | None = None, nframes: int | None = None,
                  shake: float = 0.0) -> str:
    """Leading-comma filter for a per-segment camera move on the WxH base.
    Pre-scales 2x then zoompan-samples back so the move stays sharp + smooth.
    Captions overlay AFTER this, so text never moves — only the footage does.

    ``motion`` adds a camera move: zoom_in/zoom_out use an **ease-in-out** curve (the
    pro look — accelerate then settle, not a robotic linear creep), punch is a quick
    ease-out. ``pulses`` is a list of times (seconds from segment start) for a quick
    emphasis scale-pop. ``nframes`` (segment length in frames) enables the eased curve;
    without it we fall back to the legacy linear drift."""
    if nframes and nframes > 1:
        # eased drift normalized over the segment: p in [0,1]
        p = f"clip(on/{int(nframes)},0,1)"
        eio = f"(if(lt({p},0.5),4*pow({p},3),1-pow(-2*{p}+2,3)/2))"   # ease-in-out cubic
        eo = f"(1-pow(1-{p},3))"                                       # ease-out cubic
        drift = {
            "zoom_in":  f"0.10*{eio}",
            "zoom_out": f"0.10*(1-{eio})",
            "punch":    f"0.08*{eo}",
        }
    else:
        drift = {                       # legacy linear fallback
            "zoom_in":  "min(0.00060*on,0.10)",
            "zoom_out": "max(0.10-0.00060*on,0.0)",
            "punch":    "min(0.00300*on,0.08)",
        }
    base = drift.get(motion or "", None)
    shake = max(0.0, float(shake or 0.0))
    if base is None and not pulses and shake <= 0:
        return ""
    parts = ["1.0"]
    if base is not None:
        parts.append(f"({base})")
    if shake > 0 and base is None:
        parts.append("0.06")                  # crop headroom so the shake has room to move
    if pulses:
        width = max(1.0, 0.10 * fps)          # ~100ms pop
        amp = 0.060                            # 6% scale punch
        bumps = "+".join(
            f"{amp}*exp(-pow((on-{t * fps:.1f})/{width:.1f}\\,2))" for t in pulses if t >= 0)
        if bumps:
            parts.append(f"({bumps})")
    z = "min(" + "+".join(parts) + ",1.22)"
    cx, cy = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    if shake > 0:
        a = 8.0 + 30.0 * min(1.0, shake)      # jitter amplitude (2x-input px); ~handheld feel
        cx = f"{cx}+{a:.1f}*sin(on*0.9)"
        cy = f"{cy}+{a:.1f}*cos(on*1.13)"
    return (f",scale={w * 2}:{h * 2}:flags=bicubic,"
            f"zoompan=z='{z}':d=1:x='{cx}':y='{cy}':"
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
                 speed=1.0, shake=0.0, faststart=True) -> dict:
    clip_path = Path(clip_path)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    is_img = _is_image(clip_path)
    info = probe(clip_path)
    start = max(0.0, float(start))
    if is_img:
        # still image -> a Ken Burns slot: loop for the requested length, default to a slow
        # push so it isn't static; speed/seek don't apply to a single frame.
        dur = max(0.05, float(end) - start)
        speed, motion = 1.0, (motion or "zoom_in")
    else:
        end = min(float(end), info.duration) if info.duration else float(end)
        dur = max(0.05, end - start)
        speed = max(0.1, float(speed or 1.0))
    # Speed / velocity: <1 = slow-mo, >1 = fast. We read `dur` of source and re-time it to
    # out_dur = dur/speed. speed==1.0 leaves the path byte-identical to before. Sped segments
    # are silent (music carries) to avoid pitch-shift; word captions are rescaled to match.
    sped = abs(speed - 1.0) > 1e-3
    out_dur = dur / speed
    spd = f",setpts=PTS/{speed:.4f}" if sped else ""

    rcfg = cfg.render
    mode = reframe_mode or rcfg.get("reframe_mode", "cover")
    if mode == "smart" and not is_img:
        from ..analysis.reframe_track import compute_crop_plan
        plan = compute_crop_plan(cfg, clip_path, start, end, tw, th)
        chain = tracked_chain(plan) if plan else reframe_chain(tw, th, "cover")
    else:
        chain = reframe_chain(tw, th, mode)
    motion_fc = _motion_chain(motion, tw, th, target_fps, pulses=emphasis_times,
                              nframes=int(out_dur * target_fps), shake=shake)
    g = grade_chain(cfg)
    gc = f",{g}" if g else ""
    base_chain = f"[0:v]{chain}{gc}{spd},fps={target_fps}{motion_fc}[base]"

    style = caption_style or cfg.captions.get("style", "bold-pop")
    if is_img:
        inputs = ["-loop", "1", "-t", fmt_time(out_dur), "-i", str(clip_path)]
    else:
        inputs = ["-ss", fmt_time(start), "-t", fmt_time(dur), "-i", str(clip_path)]
    cap_words = words
    if sped and words:   # remap caption word timings onto the re-timed clip
        cap_words = [{**w, "start": w["start"] / speed, "end": w["end"] / speed} for w in words]
    extra, has_overlay, caption_kind, tmpdir = _build_caption_track(
        cfg, out_dur, tw, th, target_fps, cap_words, caption_text, position, style)
    inputs += extra

    if has_overlay:
        fc = f"{base_chain};[base][1:v]overlay=0:0:shortest=1,{_NORMALIZE}[vout]"
    else:
        fc = f"[0:v]{chain}{gc}{spd},fps={target_fps}{motion_fc},{_NORMALIZE}[vout]"

    # Always emit a stereo 48k audio track (silent if the source has none) so
    # segments are concat-compatible. Map only the FIRST audio stream — iPhone
    # MOVs carry phantom audio/metadata tracks (codec "none") that break -map 0:a?.
    if info.has_audio and not mute_audio and not sped:
        audio_map = "0:a:0?"
    else:
        inputs += ["-f", "lavfi", "-t", fmt_time(out_dur),
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
    if sped:
        args += ["-t", fmt_time(out_dur)]
    if faststart:
        args += ["-movflags", "+faststart"]
    args += [str(out_path)]

    try:
        run(args, desc=f"render -> {out_path.name}")
    finally:
        if tmpdir:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)   # caption frames — don't leak per segment
    return {"caption_kind": caption_kind, "in": round(start, 3), "out": round(end, 3),
            "duration": round(dur, 3), "encoder": venc, "args": args}


def render_segment(clip_path, start, end, out_path, *, cfg, tw, th, target_fps,
                   words=None, caption_text=None, position="center", reframe_mode=None,
                   caption_style=None, mute_audio=False, motion=None, emphasis_times=None,
                   speed=1.0, shake=0.0) -> dict:
    """Render one normalized, concat-safe segment (no sidecar, no faststart)."""
    return _render_core(clip_path, start, end, out_path, cfg=cfg, tw=tw, th=th,
                        target_fps=target_fps, words=words, caption_text=caption_text,
                        position=position, reframe_mode=reframe_mode,
                        caption_style=caption_style, mute_audio=mute_audio, motion=motion,
                        emphasis_times=emphasis_times, speed=speed, shake=shake, faststart=False)


def render_vo_segment(clip_path, start, vo_wav, words, out_path, *, cfg, tw, th,
                      target_fps, position="center", caption_style=None,
                      reframe_mode=None, motion=None, emphasis_times=None, shake=0.0) -> dict:
    """Render a voiceover-driven segment: duration = VO length, captions word-synced
    to the VO, source muted, video freezes on its last frame if shorter than the VO."""
    clip_path, out_path, vo_wav = Path(clip_path), Path(out_path), Path(vo_wav)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    info = probe(clip_path)
    dur = probe(vo_wav).duration
    is_img = _is_image(clip_path)

    rcfg = cfg.render
    mode = reframe_mode or rcfg.get("reframe_mode", "cover")
    if mode == "smart" and not is_img:
        from ..analysis.reframe_track import compute_crop_plan
        plan = compute_crop_plan(cfg, clip_path, start, min(start + dur, info.duration), tw, th)
        chain = tracked_chain(plan) if plan else reframe_chain(tw, th, "cover")
    else:
        chain = reframe_chain(tw, th, mode)
    style = caption_style or cfg.captions.get("style", "bold-pop")

    # video: read from `start`, slightly past the VO; tpad clones the last frame to
    # fill any gap; output is capped to the VO duration. A still image has no timeline to
    # seek into, so loop it for the VO length instead of `-ss`/`-t` (which yields one frame).
    if is_img:
        inputs = ["-loop", "1", "-t", fmt_time(dur + 0.5), "-i", str(clip_path)]
    else:
        inputs = ["-ss", fmt_time(start), "-t", fmt_time(dur + 0.5), "-i", str(clip_path)]
    extra, has_overlay, _, cap_tmp = _build_caption_track(
        cfg, dur, tw, th, target_fps, words, None, position, style)
    inputs += extra
    inputs += ["-i", str(vo_wav)]
    vo_idx = sum(1 for x in inputs if x == "-i") - 1

    motion_fc = _motion_chain(motion, tw, th, target_fps, pulses=emphasis_times,
                              nframes=int(dur * target_fps), shake=shake)
    g = grade_chain(cfg)
    gc = f",{g}" if g else ""
    held = f"[0:v]{chain}{gc},fps={target_fps},tpad=stop_mode=clone:stop_duration={dur:.3f}{motion_fc}"
    # Hard-cap the video to the VO duration in-graph — invariant: a VO segment's video is
    # EXACTLY its voiceover length. Belt-and-suspenders with the output -t, so no source/filter
    # quirk (e.g. a generated still) can leave a frozen video tail past the audio.
    trim = f"trim=duration={dur:.3f},setpts=PTS-STARTPTS"
    if has_overlay:
        fc = f"{held}[base];[base][1:v]overlay=0:0:shortest=1,{trim},format=yuv420p[vout]"
    else:
        fc = f"{held},{trim},format=yuv420p[vout]"

    venc = pick_video_encoder(rcfg.get("hw_encoder", "h264_videotoolbox"),
                              rcfg.get("sw_encoder", "libx264"))
    args = [
        *inputs, "-filter_complex", fc, "-map", "[vout]", "-map", f"{vo_idx}:a",
        "-c:v", venc, "-b:v", str(rcfg.get("video_bitrate", "10M")),
        "-pix_fmt", "yuv420p", "-r", str(target_fps),
        "-c:a", "aac", "-b:a", str(rcfg.get("audio_bitrate", "192k")), "-ar", "48000", "-ac", "2",
        "-t", f"{dur:.3f}", "-dn", "-ignore_unknown", str(out_path),
    ]
    try:
        run(args, desc=f"vo segment -> {out_path.name}")
    finally:
        if cap_tmp:
            import shutil
            shutil.rmtree(cap_tmp, ignore_errors=True)
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
