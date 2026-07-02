"""Multi-segment timeline assembler: render an Edit Decision Plan to a video.

Each segment is rendered to a normalized, concat-safe intermediate (same res,
fps, codec, 48k stereo audio), then the segments are concatenated. Stream-copy
concat is tried first (fast, lossless); on any mismatch it falls back to a
filter `concat` re-encode.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from ..config import Config, load_config
from ..media.ffmpeg import pick_video_encoder, run
from ..media.ffprobe import probe
from .pipeline import render_segment, render_vo_segment
from ..analysis.emphasis import emphasis_pulses

# one-pass loudnorm can overshoot true peak (QC caught this on its first dogfood render).
# The trailing limiter caps sample peak at -3 dB: AAC re-encoding adds inter-sample
# overshoot (measured up to ~1.8 dB on hard-limited mixes), so -3 dB masters keep the
# encoded deliverable safely under the QC gate.
_LOUDNORM = "loudnorm=I=-14:TP=-1.5:LRA=11,alimiter=limit=0.71:level=disabled"


def _resolve_caption(cfg: Config, seg: dict):
    """Return (words, caption_text) for a segment's caption directive."""
    cap = seg.get("caption", "auto")
    if cap == "auto":
        from ..analysis.transcribe import transcribe_cached, words_in_range
        tr = transcribe_cached(cfg, seg["source"])
        return _normalize_caption_words(words_in_range(tr["words"], seg["in"], seg["out"])), None
    if isinstance(cap, dict) and cap.get("text"):
        return None, cap["text"]
    if isinstance(cap, str) and cap not in ("auto", "none"):
        return None, cap
    return None, None


# Brand display spellings — Whisper mishears these; force the on-screen brand form.
_BRAND_CAPTION = {
    "catty": "Caddy", "caddy": "Caddy", "quarketti": "Court Caddy",
    "ranger": "Ranger", "rangers": "Rangers",
    "forward": "FORWRD", "forwrd": "FORWRD",
}


def _normalize_caption_words(words: list[dict]) -> list[dict]:
    """Re-join words the TTS lexicon split (e.g. spoken "pickle ball" -> caption
    "pickleball") and apply brand display spellings (Court Caddy, FORWRD)."""
    import re

    def base(w: str) -> str:
        return re.sub(r"[^a-z]", "", w.lower())

    def trail(w: str) -> str:
        m = re.search(r"[.,!?]+$", w)
        return m.group(0) if m else ""

    out, i, n = [], 0, len(words)
    while i < n:
        w = words[i]
        if i + 1 < n and base(w["word"]) == "pickle" and base(words[i + 1]["word"]) == "ball":
            nxt = words[i + 1]
            out.append({"start": w["start"], "end": nxt["end"],
                        "word": "pickleball" + trail(nxt["word"])})
            i += 2
        elif i + 1 < n and base(w["word"]) == "forward" and base(words[i + 1]["word"]) == "co":
            # spoken "forward dot co" -> brand spelling on screen
            nxt = words[i + 1]
            out.append({"start": w["start"], "end": nxt["end"], "word": "FORWRD.CO"})
            i += 2
        elif i + 1 < n and base(w["word"]) in ("court", "core") and base(words[i + 1]["word"]) in ("catty", "caddy", "kitty"):
            # Whisper mishears "Court Caddy" as "court catty / core caddy" — force the brand spelling
            nxt = words[i + 1]
            out.append({"start": w["start"], "end": nxt["end"],
                        "word": "Court Caddy" + trail(nxt["word"])})
            i += 2
        elif i + 1 < n and words[i + 1]["word"].startswith("-") and any(c.isalnum() for c in words[i + 1]["word"]):
            # rejoin hyphenated compounds Whisper splits: "30"+"-day", "money"+"-back", "pre"+"-order"
            nxt = words[i + 1]
            out.append({"start": w["start"], "end": nxt["end"], "word": w["word"] + nxt["word"]})
            i += 2
        else:
            out.append(w)
            i += 1
    fixed = []
    for w in out:
        b = base(w["word"])
        if b in _BRAND_CAPTION:
            fixed.append({**w, "word": _BRAND_CAPTION[b] + trail(w["word"])})
        else:
            fixed.append(w)
    return fixed


_SEG_CACHE_SALT = "seg-v1"      # bump when segment-render semantics change


def _segment_key(cfg: Config, job: dict, tw: int, th: int, fps: int, position: str,
                 cap_style: str | None, mute: bool, voice: str | None) -> str:
    """Content hash of everything that affects one rendered segment. Same key ==
    byte-equivalent segment -> safe to reuse across renders (incremental editing:
    change one beat, re-render one beat)."""
    from .grade import grade_chain
    seg = job["seg"]
    src = Path(seg["source"])
    try:
        st = src.stat()
        src_id = [str(src.resolve()), st.st_mtime_ns, st.st_size]
    except OSError:
        src_id = [str(src), 0, 0]
    material = {
        "salt": _SEG_CACHE_SALT, "kind": job["kind"], "src": src_id,
        "in": seg.get("in"), "out": seg.get("out"),
        "reframe": seg.get("reframe"), "motion": job["motion"], "shake": job["shake"],
        "speed": job.get("speed", 1.0), "emph": job.get("emph"),
        "vo": seg.get("voiceover"), "voice": voice, "mute": mute,
        "words": hashlib.sha1(json.dumps(job.get("words") or [],
                                         sort_keys=True).encode()).hexdigest(),
        "caption_text": job.get("caption_text"),
        "target": [tw, th, fps], "position": position, "style": cap_style,
        "grade": grade_chain(cfg), "captions_cfg": cfg.captions,
        "enc": [cfg.render.get("hw_encoder"), cfg.render.get("sw_encoder"),
                cfg.render.get("video_bitrate"), cfg.render.get("audio_bitrate")],
    }
    return hashlib.sha1(json.dumps(material, sort_keys=True, default=str).encode()).hexdigest()[:24]


def render_timeline(edp: dict, out_path: str | Path, cfg: Config | None = None,
                    *, preview: bool = False) -> dict:
    cfg = cfg or load_config()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rcfg = cfg.render
    tgt = edp.get("target", {})

    if preview:
        tw, th = int(rcfg.get("preview_width", 540)), int(rcfg.get("preview_height", 960))
    else:
        tw = int(tgt.get("width", rcfg.get("target_width", 1080)))
        th = int(tgt.get("height", rcfg.get("target_height", 1920)))
    fps = int(tgt.get("fps") or rcfg.get("fps") or 30) or 30
    position = edp.get("captions", {}).get("position", "center")
    cap_style = edp.get("captions", {}).get("style")
    mute = bool(edp.get("mute_source", False))

    voice = edp.get("voice")
    # Creative default: give every shot subtle life (alternating slow push in/out)
    # unless the EDP/segment opts out. Keeps static talking heads + b-roll "sticky".
    auto_motion = edp.get("auto_motion", True)

    tmpdir = Path(tempfile.mkdtemp(prefix="forwrdcut_tl_"))

    # ---- PREPARE (serial): resolve everything deterministic per segment ------------
    # Transcription/TTS are cached and NOT thread-safe on first model load, so all of
    # that happens here; the expensive ffmpeg renders then run in parallel below.
    jobs: list[dict] = []
    for i, seg in enumerate(edp["segments"]):
        default_mtn = ("zoom_in" if i % 2 == 0 else "zoom_out") if auto_motion else None
        mtn = seg.get("motion", default_mtn)
        emph_on = seg.get("emphasis", edp.get("emphasis", False))
        job = {"i": i, "seg": seg, "motion": mtn, "shake": float(seg.get("shake", 0.0))}
        if seg.get("voiceover"):
            from ..audio.tts import synthesize
            from ..analysis.transcribe import transcribe
            # cache VO + word timings by (voice, line) so 9:16 / 4:5 reuse them
            key = hashlib.sha1(f"{voice}|{seg['voiceover']}".encode()).hexdigest()[:16]
            vocache = cfg.cache_dir / "vo"
            vocache.mkdir(parents=True, exist_ok=True)
            vo, wj = vocache / f"{key}.wav", vocache / f"{key}.json"
            if not vo.exists():
                synthesize(seg["voiceover"], vo, cfg=cfg, voice=voice)
            if wj.exists():
                words = json.loads(wj.read_text())
            else:
                words = transcribe(vo, cfg)["words"]
                wj.write_text(json.dumps(words))
            words = _normalize_caption_words(words)
            # emphasis from the VO words (relative to the VO start), before any suppression
            emph = emphasis_pulses(words, 0.0, 1e9) if emph_on else None
            # caption:"none" suppresses the word-synced VO captions (e.g. when a big
            # designed callout overlay carries the on-screen text instead).
            if seg.get("caption") == "none":
                words = []
            job.update(kind="vo", vo_wav=str(vo), words=words, emph=emph)
        else:
            words, caption_text = _resolve_caption(cfg, seg)
            emph = emphasis_pulses(words, seg["in"], seg["out"]) if (emph_on and words) else None
            job.update(kind="seg", words=words, caption_text=caption_text, emph=emph,
                       speed=float(seg.get("speed", 1.0)))
        job["key"] = _segment_key(cfg, job, tw, th, fps, position, cap_style, mute, voice)
        jobs.append(job)

    # ---- RENDER (parallel, cached): editing one beat re-renders one beat -----------
    use_cache = bool(rcfg.get("segment_cache", True)) and not preview
    seg_cache = cfg.cache_dir / "segments"
    seg_cache.mkdir(parents=True, exist_ok=True)

    def _dest(job) -> Path:
        return (seg_cache / f"{job['key']}.mp4") if use_cache \
            else (tmpdir / f"seg_{job['i']:03d}.mp4")

    def _render_job(job) -> None:
        dest = _dest(job)
        if use_cache and dest.exists():
            return
        work = dest.with_suffix(".part.mp4")     # atomic: never leave a torn cache entry
        seg, mtn = job["seg"], job["motion"]
        if job["kind"] == "vo":
            render_vo_segment(seg["source"], seg["in"], job["vo_wav"], job["words"], work,
                              cfg=cfg, tw=tw, th=th, target_fps=fps, position=position,
                              caption_style=cap_style, reframe_mode=seg.get("reframe"),
                              motion=mtn, emphasis_times=job["emph"], shake=job["shake"])
        else:
            render_segment(seg["source"], seg["in"], seg["out"], work, cfg=cfg, tw=tw, th=th,
                           target_fps=fps, words=job["words"], caption_text=job["caption_text"],
                           position=position, reframe_mode=seg.get("reframe"),
                           caption_style=cap_style, mute_audio=mute, motion=mtn,
                           emphasis_times=job["emph"], speed=job["speed"], shake=job["shake"])
        work.replace(dest)

    todo = [j for j in jobs if not (use_cache and _dest(j).exists())]
    workers = max(1, int(rcfg.get("parallel_workers", min(4, (os.cpu_count() or 2) // 2))))
    if len(todo) > 1 and workers > 1:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=workers) as ex:
            list(ex.map(_render_job, todo))      # list() re-raises any worker exception
    else:
        for j in todo:
            _render_job(j)
    parts: list[Path] = [_dest(j) for j in jobs]

    cues = edp.get("sfx") or []
    do_sfx = bool(cues) and bool(cfg.data.get("sfx", {}).get("enabled", True))
    music = edp.get("music") or {}
    if music and not music.get("file") and music.get("mood"):
        # resolve a mood to a real track: licensed library first, procedural bed fallback
        from ..audio.music import pick_music
        total_guess = sum(probe(p).duration or 0 for p in parts)
        track = pick_music(cfg, mood=music["mood"], min_duration=min(total_guess, 20.0))
        music = {**music, "file": track["path"]}
    do_music = bool(music.get("file")) and Path(music["file"]).exists()
    concat_out = tmpdir / "_concat.mp4"

    # Optional crossfade/dissolve transitions (xfade). Default is hard cuts.
    _TRANS_ALIAS = {"crossfade": "fade", "dissolve": "fade"}
    xtype = _TRANS_ALIAS.get(edp.get("transition"), edp.get("transition"))
    xdur = float(edp.get("transition_duration", 0.4))
    if xtype and xtype not in ("cut", "none") and len(parts) > 1:
        durs = [probe(p).duration for p in parts]
        venc = pick_video_encoder(rcfg.get("hw_encoder", "h264_videotoolbox"),
                                  rcfg.get("sw_encoder", "libx264"))
        args = []
        for p in parts:
            args += ["-i", str(p)]
        chain, vlab, alab, acc = [], "0:v", "0:a", durs[0]
        for i in range(1, len(parts)):
            off = max(0.0, acc - xdur)
            v2, a2 = f"vx{i}", f"ax{i}"
            chain.append(f"[{vlab}][{i}:v]xfade=transition={xtype}:duration={xdur}:offset={off:.3f}[{v2}]")
            chain.append(f"[{alab}][{i}:a]acrossfade=d={xdur}[{a2}]")
            vlab, alab = v2, a2
            acc += durs[i] - xdur
        args += ["-filter_complex", ";".join(chain), "-map", f"[{vlab}]", "-map", f"[{alab}]",
                 "-c:v", venc, "-b:v", str(rcfg.get("video_bitrate", "10M")),
                 "-pix_fmt", "yuv420p", "-r", str(fps),
                 "-c:a", "aac", "-b:a", str(rcfg.get("audio_bitrate", "192k")),
                 "-ar", "48000", "-ac", "2", "-movflags", "+faststart", str(concat_out)]
        run(args, desc=f"concat (xfade {xtype})")
    else:
        listfile = tmpdir / "list.txt"
        listfile.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts))
        try:
            run(["-f", "concat", "-safe", "0", "-i", str(listfile), "-c", "copy",
                 "-movflags", "+faststart", str(concat_out)], desc="concat (copy)")
        except Exception:
            venc = pick_video_encoder(rcfg.get("hw_encoder", "h264_videotoolbox"),
                                      rcfg.get("sw_encoder", "libx264"))
            args = []
            for p in parts:
                args += ["-i", str(p)]
            n = len(parts)
            fc = "".join(f"[{i}:v][{i}:a]" for i in range(n)) + f"concat=n={n}:v=1:a=1[v][a]"
            args += ["-filter_complex", fc, "-map", "[v]", "-map", "[a]",
                     "-c:v", venc, "-b:v", str(rcfg.get("video_bitrate", "10M")),
                     "-pix_fmt", "yuv420p", "-r", str(fps),
                     "-c:a", "aac", "-b:a", str(rcfg.get("audio_bitrate", "192k")),
                     "-ar", "48000", "-ac", "2", "-movflags", "+faststart", str(concat_out)]
            run(args, desc="concat (filter re-encode)")

    current = concat_out
    if do_sfx:
        from .sfx import mix_into
        nxt = tmpdir / "_sfx.mp4"
        mix_into(current, cues, nxt, cfg)
        current = nxt
    if do_music:
        from .sfx import mix_music
        nxt = tmpdir / "_music.mp4"
        mix_music(current, music["file"], nxt, cfg,
                  gain=music.get("gain"), duck=music.get("duck", True))
        current = nxt
    # ---- SINGLE-PASS FINISH ------------------------------------------------------
    # Cinematic look + graphic overlays + loudnorm all happen in ONE encode (they used
    # to be up to three sequential passes — each a generation of quality loss). The
    # look chain runs first so text/badges sit on top of letterbox bars. -shortest
    # guarantees the output length matches the audio spine (no frozen-tail survives).
    from .looks import build_look_graph
    look = build_look_graph(edp)
    overlays = edp.get("overlays") or []
    specs = []
    if overlays:
        from .graphics import build_overlay_specs
        total = probe(current).duration
        specs = build_overlay_specs(overlays, (tw, th), total, cfg, tmpdir)
    loudnorm = bool(edp.get("loudnorm"))

    if not look and not specs:
        # nothing visual to burn: stream-copy video; loudnorm (audio-only encode) if asked
        if loudnorm:
            run(["-i", str(current), "-af", _LOUDNORM,
                 "-c:v", "copy", "-c:a", "aac", "-b:a", str(rcfg.get("audio_bitrate", "192k")),
                 "-shortest", "-movflags", "+faststart", str(out_path)],
                desc="finalize + loudnorm")
        else:
            run(["-i", str(current), "-c", "copy", "-shortest", "-movflags", "+faststart",
                 str(out_path)], desc="finalize")
    else:
        venc = pick_video_encoder(rcfg.get("hw_encoder", "h264_videotoolbox"),
                                  rcfg.get("sw_encoder", "libx264"))
        args = ["-i", str(current)]
        chain, lab = [], "0:v"
        if look:
            # the look graph ends "[vout]"; relabel it so overlays can chain after it
            chain.append(look[:-len("[vout]")] + "[lkbase]" if specs else look)
            lab = "lkbase" if specs else "vout"
        for i, s in enumerate(specs, start=1):
            # loop each still PNG across the whole clip so timed/enable-gated and
            # t-animated (progress) overlays persist past frame 0
            args += ["-loop", "1", "-t", f"{total:.3f}", "-i", str(s["png"])]
            o = f"g{i}"
            en = f":enable='{s['enable']}'" if s.get("enable") else ""
            chain.append(f"[{i}:v]format=rgba[ov{i}]")
            chain.append(f"[{lab}][ov{i}]overlay=x={s['x']}:y={s['y']}:eval=frame{en}[{o}]")
            lab = o
        if lab != "vout":
            chain.append(f"[{lab}]format=yuv420p[vout]")
        amap = ["-map", "0:a?", "-c:a", "copy"]
        if loudnorm:
            chain.append(f"[0:a]{_LOUDNORM}[aout]")
            amap = ["-map", "[aout]", "-c:a", "aac", "-b:a", str(rcfg.get("audio_bitrate", "192k")),
                    "-ar", "48000", "-ac", "2"]
        args += ["-filter_complex", ";".join(chain), "-map", "[vout]", *amap,
                 "-c:v", venc, "-b:v", str(rcfg.get("video_bitrate", "10M")),
                 "-pix_fmt", "yuv420p", "-shortest", "-movflags", "+faststart", str(out_path)]
        run(args, desc="finish (look+overlays+loudnorm, single pass)")

    edp_out = dict(edp)
    edp_out["_render"] = {
        "output": str(out_path), "target": [tw, th], "fps": fps, "preview": preview,
        "segments": len(parts),
        "rendered_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    sidecar = out_path.with_suffix(out_path.suffix + ".edp.json")
    sidecar.write_text(json.dumps(edp_out, indent=2))

    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)   # segments/overlay PNGs — no per-render leak

    info = probe(out_path)
    return {
        "output": str(out_path), "sidecar": str(sidecar), "segments": len(parts),
        "duration": info.duration, "resolution": f"{info.width}x{info.height}",
        "size_bytes": info.size_bytes,
    }
