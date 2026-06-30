"""FORWRDCUT command-line interface.

Subcommands:
  scan                 Index the source library (ffprobe + SQLite cache)
  info  <file>         Print probe details for one file as JSON
  clips                List indexed clips from the cache
  slice                Render one trim → 9:16 → caption → HW-encode slice
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import load_config
from .media.ffmpeg import assert_tools
from .media.ffprobe import probe


def _apply_overrides(edp: dict, args) -> dict:
    """Apply CLI --style / --music overrides onto a generated plan."""
    if getattr(args, "style", None):
        edp.setdefault("captions", {})["style"] = args.style
    if getattr(args, "music", None):
        edp["music"] = {"file": args.music, "duck": True}
    return edp


def cmd_scan(args) -> int:
    from .analysis.scan import scan_library

    cfg = load_config(args.config)
    print(f"Scanning {cfg.source_dir} ...")
    clips = scan_library(cfg, force=args.force)
    if not clips:
        print("No videos found. Drop or symlink clips into the source folder.")
        return 0
    for c in clips:
        print("  -", c.summary())
    print(f"\n{len(clips)} clip(s) indexed -> {cfg.db_path}")
    return 0


def cmd_info(args) -> int:
    print(json.dumps(probe(args.file).to_dict(), indent=2))
    return 0


def cmd_clips(args) -> int:
    from . import project

    cfg = load_config(args.config)
    con = project.connect(cfg.db_path)
    try:
        rows = project.all_clips(con)
    finally:
        con.close()
    for c in rows:
        print(f"  - {c['filename']:45.45s} {c['width']}x{c['height']:<6} "
              f"{c['orientation']:<9} {c['duration']:.1f}s  audio={'Y' if c['has_audio'] else 'N'}")
    print(f"\n{len(rows)} clip(s) in index.")
    return 0


def cmd_transcribe(args) -> int:
    from .analysis.transcribe import transcribe_cached

    cfg = load_config(args.config)
    print(f"Transcribing {Path(args.clip).name} (this downloads the model on first run)…")
    tr = transcribe_cached(cfg, args.clip, force=args.force)
    print(f"\nLanguage: {tr['language']}   Words: {len(tr['words'])}\n")
    print(tr["full_text"][:1200])
    if args.json:
        print("\n--- words ---")
        print(json.dumps(tr["words"], indent=2))
    return 0


def cmd_plan(args) -> int:
    from .strategy.planner import plan_clip
    from .strategy import edp as edpmod

    cfg = load_config(args.config)
    from .strategy.trends import load_trends
    trends = load_trends(cfg, args.platform, cfg.brand.get("niche", ""))
    if trends:
        print(f"  grounding in trends from {trends.get('fetched_at')}"
              f"{' (STALE)' if trends.get('_stale') else ''}")
    print(f"Planning {Path(args.clip).name} for {args.platform}…")
    edp = plan_clip(cfg, args.clip, platform=args.platform, target_seconds=args.seconds,
                    trends=trends, refine=not args.no_refine, force=args.force)
    _apply_overrides(edp, args)
    print("\n" + edpmod.pretty(edp))
    out = Path(args.out) if args.out else (cfg.output_dir / f"{edp['project']}.edp.json")
    edpmod.save(edp, out)
    print(f"\nPlan saved -> {out}")
    print(f"Render it with:  forwrdcut render-plan \"{out}\"")
    return 0


def cmd_render_plan(args) -> int:
    from .render.timeline import render_timeline
    from .strategy import edp as edpmod

    cfg = load_config(args.config)
    edp = edpmod.load(args.plan)
    errs = edpmod.validate(edp)
    if errs:
        print("Plan validation errors:")
        for e in errs:
            print("  -", e)
        return 2
    out = (Path(args.out) if args.out else
           (cfg.preview_dir if args.preview else cfg.output_dir)
           / f"{edp.get('project', 'plan')}_9x16{'_preview' if args.preview else ''}.mp4")
    print(f"Rendering plan ({len(edp['segments'])} segments) -> {out.name}")
    res = render_timeline(edp, out, cfg, preview=args.preview)
    print("\n✓ Timeline rendered")
    for k, v in res.items():
        print(f"  {k:12s}: {v}")
    return 0


def cmd_auto(args) -> int:
    from .strategy.planner import plan_clip
    from .strategy import edp as edpmod
    from .render.timeline import render_timeline

    cfg = load_config(args.config)
    from .strategy.trends import load_trends
    trends = load_trends(cfg, args.platform, cfg.brand.get("niche", ""))
    print(f"AUTO: {Path(args.clip).name} -> {args.platform}"
          + (f"  (trends {trends.get('fetched_at')})" if trends else ""))
    edp = plan_clip(cfg, args.clip, platform=args.platform, target_seconds=args.seconds,
                    trends=trends, refine=not args.no_refine, force=args.force)
    _apply_overrides(edp, args)
    print("\n" + edpmod.pretty(edp))
    out = ((cfg.preview_dir if args.preview else cfg.output_dir)
           / f"{edp['project']}_9x16{'_preview' if args.preview else ''}.mp4")
    res = render_timeline(edp, out, cfg, preview=args.preview)
    print("\n✓ Done")
    for k, v in res.items():
        print(f"  {k:12s}: {v}")
    return 0


def cmd_short(args) -> int:
    from .strategy.autoedit import autoedit

    cfg = load_config(args.config)
    target = {"9x16": {"width": 1080, "height": 1920, "fps": 30},
              "16x9": {"width": 1920, "height": 1080, "fps": 30},
              "1x1":  {"width": 1080, "height": 1080, "fps": 30}}[args.aspect]
    out = (Path(args.out) if args.out
           else cfg.output_dir / f"{Path(args.clip).stem}_short_{args.aspect}.mp4")
    print(f"SHORT (autonomous): {Path(args.clip).name} -> {args.platform} {args.aspect}")
    res = autoedit(cfg, args.clip, out, platform=args.platform, target_seconds=args.seconds,
                   music_style=args.music_style, target=target, reframe=args.reframe,
                   beat_sync=not args.no_beat_sync)
    print("\n✓ Done")
    for k, v in res.items():
        print(f"  {k:12s}: {v}")
    return 0


def cmd_template(args) -> int:
    from .strategy.templates import render_template

    cfg = load_config(args.config)
    out = Path(args.out) if args.out else cfg.output_dir / f"{args.name}_{args.aspect}.mp4"
    print(f"TEMPLATE {args.name}: {len(args.clips)} clips -> {args.aspect}")
    res = render_template(cfg, args.name, args.clips, out, aspect=args.aspect,
                          music_style=args.music_style, headlines=args.headline,
                          cinematic=args.cinematic)
    print("\n✓ Done")
    for k, v in res.items():
        print(f"  {k:12s}: {v}")
    return 0


def cmd_batch(args) -> int:
    from .strategy.batch import make_batch
    from .strategy import edp as edpmod
    from .strategy.trends import load_trends
    from .render.timeline import render_timeline

    cfg = load_config(args.config)
    trends = load_trends(cfg, args.platform, cfg.brand.get("niche", ""))
    print(f"BATCH: up to {args.n} {args.platform} clip(s)"
          + (f"  (trends {trends.get('fetched_at')})" if trends else ""))
    clips = args.clips or None
    if not clips and getattr(args, "source", None):
        from .analysis.scan import iter_videos
        clips = [str(p) for p in iter_videos(Path(args.source))]
        print(f"  source folder: {args.source}  ({len(clips)} video(s) found)")
        if not clips:
            print("No videos found in that folder."); return 1
    plans = make_batch(cfg, platform=args.platform, n=args.n, trends=trends,
                       seconds=args.seconds, clips=clips)
    if not plans:
        print("No usable clips found. Run `forwrdcut scan` and add footage to media/source/.")
        return 1
    results = []
    for i, edp in enumerate(plans, 1):
        _apply_overrides(edp, args)
        out = ((cfg.preview_dir if args.preview else cfg.output_dir)
               / f"{edp['project']}_9x16{'_preview' if args.preview else ''}.mp4")
        print(f"\n[{i}/{len(plans)}] {edp['project']}  "
              f"({edpmod.total_duration(edp)}s, {len(edp['segments'])} segs)  "
              f"hook: {edp['hook']['text'][:48]}")
        res = render_timeline(edp, out, cfg, preview=args.preview)
        print(f"   -> {res['output']}  ({res['resolution']}, {res['duration']:.1f}s)")
        results.append(res)
    print(f"\n✓ {len(results)} clip(s) rendered to {cfg.output_dir}")
    return 0


def cmd_analyze(args) -> int:
    from .analysis.scoring import analyze_clip, top_nonoverlapping

    cfg = load_config(args.config)
    print(f"Analyzing {Path(args.clip).name} (scenes + audio + transcript + scoring)…")
    a = analyze_clip(cfg, args.clip, force=args.force)
    print(f"\n{a['filename']}  {a['resolution']} {a['orientation']}  {a['duration']:.1f}s  "
          f"scenes={a['n_scenes']}  audio={'Y' if a['has_audio'] else 'N'}  lang={a['language']}")

    if a["hooks"]:
        print("\nTop hook lines:")
        for h in a["hooks"][:5]:
            print(f"  [{h['score']:>4.1f}]  {h['start']:5.1f}-{h['end']:<5.1f}s  {h['text']}")

    print("\nTop highlight windows:")
    for w in top_nonoverlapping(a["highlights"], 3):
        print(f"  [{w['score']:>4.1f}]  {w['start']:5.1f}-{w['end']:<5.1f}s  "
              f"words={w['words']} cuts={w['cuts']} active={w['active']}")

    if args.render:
        from .render.pipeline import render_slice
        from .analysis.transcribe import transcribe_cached, words_in_range

        top = top_nonoverlapping(a["highlights"], 1)[0]
        s, e = top["start"], top["end"]
        words = None
        if a["has_audio"]:
            words = words_in_range(transcribe_cached(cfg, args.clip)["words"], s, e)
        out = cfg.output_dir / f"{Path(args.clip).stem}_auto_9x16.mp4"
        print(f"\nAuto-rendering top highlight [{s:.1f}-{e:.1f}s] -> {out.name}")
        res = render_slice(args.clip, s, e, None, out, words=words, cfg=cfg, position="center")
        for k, v in res.items():
            print(f"  {k:12s}: {v}")
    return 0


def cmd_slice(args) -> int:
    from .render.pipeline import render_slice

    cfg = load_config(args.config)
    clip = Path(args.clip)
    if not clip.exists():
        print(f"Clip not found: {clip}", file=sys.stderr)
        return 2

    start = float(args.start)
    if args.end is not None:
        end = float(args.end)
    elif args.duration is not None:
        end = start + float(args.duration)
    else:
        end = start + 6.0

    if args.out:
        out = Path(args.out)
    else:
        base = cfg.preview_dir if args.preview else cfg.output_dir
        suffix = "_preview" if args.preview else ""
        out = base / f"{clip.stem}_tiktok_9x16{suffix}.mp4"

    words = None
    if args.auto_captions:
        from .analysis.transcribe import transcribe_cached, words_in_range
        print("Transcribing for word-synced captions…")
        tr = transcribe_cached(cfg, clip)
        words = words_in_range(tr["words"], start, end)
        print(f"  {len(words)} word(s) in [{start:.2f}s, {end:.2f}s]")
        if not words:
            print("  ! no speech in range; using --text fallback" if args.text
                  else "  ! no speech in range; rendering without captions")

    cap_desc = "auto-captions" if words else (f"text={args.text!r}" if args.text else "no captions")
    print(f"Rendering {clip.name}  [{start:.2f}s -> {end:.2f}s]  {cap_desc}")
    res = render_slice(
        clip, start, end, args.text, out, words=words,
        cfg=cfg, preview=args.preview, position=args.position, reframe_mode=args.reframe,
        caption_style=args.style,
    )
    print("\n✓ Render complete")
    for k, v in res.items():
        print(f"  {k:12s}: {v}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="forwrdcut", description="Local AI video editor")
    p.add_argument("--config", default=None, help="path to config.toml")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("scan", help="index the source library")
    sp.add_argument("--force", action="store_true", help="re-probe even if unchanged")
    sp.set_defaults(func=cmd_scan)

    sp = sub.add_parser("info", help="probe one file")
    sp.add_argument("file")
    sp.set_defaults(func=cmd_info)

    sp = sub.add_parser("clips", help="list indexed clips")
    sp.set_defaults(func=cmd_clips)

    sp = sub.add_parser("transcribe", help="transcribe a clip (word-level timestamps, cached)")
    sp.add_argument("clip")
    sp.add_argument("--force", action="store_true", help="ignore cache")
    sp.add_argument("--json", action="store_true", help="also dump word timings")
    sp.set_defaults(func=cmd_transcribe)

    sp = sub.add_parser("analyze", help="scenes + audio + transcript + highlight scoring")
    sp.add_argument("clip")
    sp.add_argument("--force", action="store_true", help="ignore caches")
    sp.add_argument("--render", action="store_true",
                    help="auto-render the top highlight with word-synced captions")
    sp.set_defaults(func=cmd_analyze)

    def _plan_args(p):
        p.add_argument("clip")
        p.add_argument("--platform", default="tiktok", choices=["tiktok", "reels", "shorts"])
        p.add_argument("--seconds", default=None, type=float, help="target length")
        p.add_argument("--style", default=None,
                       choices=["bold-pop", "karaoke", "clean-minimal"], help="caption style")
        p.add_argument("--music", default=None, help="music bed file (mixed under speech)")
        p.add_argument("--no-refine", action="store_true", help="skip optional Claude hook polish")
        p.add_argument("--force", action="store_true", help="ignore analysis caches")

    sp = sub.add_parser("plan", help="analysis → Edit Decision Plan (saved as JSON)")
    _plan_args(sp)
    sp.add_argument("--out", default=None)
    sp.set_defaults(func=cmd_plan)

    sp = sub.add_parser("render-plan", help="render an Edit Decision Plan JSON to video")
    sp.add_argument("plan")
    sp.add_argument("--out", default=None)
    sp.add_argument("--preview", action="store_true", help="fast low-res render")
    sp.set_defaults(func=cmd_render_plan)

    sp = sub.add_parser("auto", help="plan + render in one step")
    _plan_args(sp)
    sp.add_argument("--preview", action="store_true", help="fast low-res render")
    sp.set_defaults(func=cmd_auto)

    sp = sub.add_parser("short", help="autonomous one-call edit: raw clip -> finished Short")
    sp.add_argument("--clip", required=True)
    sp.add_argument("--platform", default="tiktok", choices=["tiktok", "reels", "shorts", "youtube"])
    sp.add_argument("--seconds", default=24.0, type=float, help="target length")
    sp.add_argument("--aspect", default="9x16", choices=["9x16", "16x9", "1x1"])
    sp.add_argument("--music-style", dest="music_style", default="driving",
                    choices=["upbeat", "driving", "chill"])
    sp.add_argument("--reframe", default="cover", choices=["cover", "blur_pad", "smart"])
    sp.add_argument("--no-beat-sync", dest="no_beat_sync", action="store_true",
                    help="disable beat-aligned cuts")
    sp.add_argument("--out", default=None)
    sp.set_defaults(func=cmd_short)

    sp = sub.add_parser("template", help="fill a beat-timed template with your clips and render")
    sp.add_argument("--name", required=True, choices=["beat_slideshow", "feature_showcase"])
    sp.add_argument("--clips", nargs="+", required=True, help="clip paths to drop into the slots")
    sp.add_argument("--aspect", default="9x16", choices=["9x16", "16x9", "1x1"])
    sp.add_argument("--music-style", dest="music_style", default="driving",
                    choices=["upbeat", "driving", "chill"])
    sp.add_argument("--headline", action="append", default=[],
                    help="callout per clip for feature_showcase (repeat; *word* = orange)")
    sp.add_argument("--cinematic", action="store_true", help="apply letterbox + vignette look")
    sp.add_argument("--out", default=None)
    sp.set_defaults(func=cmd_template)

    sp = sub.add_parser("batch", help='"make me N TikToks" — pick best clips, render each')
    sp.add_argument("--n", default=3, type=int, help="how many clips to produce")
    sp.add_argument("--platform", default="tiktok", choices=["tiktok", "reels", "shorts"])
    sp.add_argument("--seconds", default=None, type=float, help="target length per clip")
    sp.add_argument("--clips", nargs="*", default=None, help="explicit clip paths (else whole library)")
    sp.add_argument("--source", default=None, help="process every video in this folder")
    sp.add_argument("--style", default=None, choices=["bold-pop", "karaoke", "clean-minimal"])
    sp.add_argument("--music", default=None, help="music bed file (mixed under speech)")
    sp.add_argument("--preview", action="store_true", help="fast low-res renders")
    sp.set_defaults(func=cmd_batch)

    sp = sub.add_parser("slice", help="render a trim+caption+9:16 slice")
    sp.add_argument("--clip", required=True)
    sp.add_argument("--start", default=0.0, type=float)
    sp.add_argument("--end", default=None, type=float)
    sp.add_argument("--duration", default=None, type=float)
    sp.add_argument("--text", default=None, help="static caption / hook text")
    sp.add_argument("--auto-captions", action="store_true",
                    help="transcribe and burn word-synced animated captions")
    sp.add_argument("--out", default=None)
    sp.add_argument("--preview", action="store_true", help="fast low-res render")
    sp.add_argument("--position", default="lower", choices=["lower", "center", "upper"])
    sp.add_argument("--reframe", default=None, choices=["cover", "blur_pad", "smart"])
    sp.add_argument("--style", default=None, choices=["bold-pop", "karaoke", "clean-minimal"])
    sp.set_defaults(func=cmd_slice)

    return p


def main(argv=None) -> int:
    assert_tools()
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
