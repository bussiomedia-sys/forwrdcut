"""Project scaffolding — `forwrdcut init` and `forwrdcut doctor`.

Everything a fresh user needs to go from `pip install` to a working editor:
init writes a neutral config + folder layout + an example brand kit into the
current directory; doctor verifies the environment and says exactly what to fix.
Templates are embedded (not read from the repo) so pip installs work anywhere.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

CONFIG_TEMPLATE = """\
# ForwrdCut project configuration — edit to taste. Paths resolve relative to this file.

[brand]
name = "yourbrand"                  # your brand/channel name
niche = "your niche"                # drives trend research grounding
platforms = ["tiktok", "reels", "shorts"]

[paths]
source_dir = "media/source"         # READ-ONLY. Put (or symlink) source clips here.
output_dir = "renders"
preview_dir = "renders/previews"
cache_dir = "cache"
db_path = "cache/library.db"
sfx_dir = "assets/sfx"
trends_dir = "cache/trends"

[render]
hw_encoder = "h264_videotoolbox"    # Apple Silicon HW encode; auto-falls back to sw_encoder
sw_encoder = "libx264"              # used automatically on Linux/Windows/Intel
target_width = 1080
target_height = 1920                # 9:16 vertical default
fps = 30
video_bitrate = "10M"
audio_bitrate = "192k"
preview_width = 540
preview_height = 960
reframe_mode = "cover"              # cover (center smart-crop) | blur_pad
segment_cache = true                # incremental renders: edit one beat, re-render one beat

[captions]
style = "box-pop"                   # box-pop | bold-pop | karaoke | clean-minimal
font = "auto"                       # "auto" finds a bold system font; or path to a .ttf
fill = "#FFFFFF"
stroke = "#000000"
highlight = "#EA6024"               # emphasis-word accent (brand kits override per-EDP)
# platform SAFE ZONES (fraction of frame) — keeps captions clear of feed UI:
safe_top_frac = 0.13
safe_bottom_frac = 0.24
safe_side_frac = 0.08

[grade]
enabled = true
preset = "punch"                    # punch | warm | vibrant | clean
# lut = "assets/luts/your.cube"     # optional custom LUT

[sfx]
enabled = true
gain = 0.55

[music]
gain = 0.12
duck = true
# licensed_dir = "assets/music/licensed"   # drop licensed tracks here (never commit them)

[library]
# expected_terms = ["yourbrand", "your product"]   # `forwrdcut audit` junk detection

[reframe]
smart = true
pan = true
sample_fps = 3.0
min_face_ratio = 0.35

[transcription]
model = "small"                     # faster-whisper: tiny|base|small|medium|large-v3
language = "en"
compute_type = "int8"

[vision]
enabled = false                     # set true + ANTHROPIC_API_KEY for vision descriptions
model = "claude-opus-4-8"
"""

BRAND_EXAMPLE = """\
# Brand kit — rename to your brand and set `"brand": "<name>"` in your EDPs.
# Styles the render (accent) and LINTS the copy against [claims].approved.

[brand]
name = "Example Co"
url = "example.com"

[style]
highlight = "#EA6024"

[voice]
no_em_dash = true
banned_words = ["best", "revolutionary", "disruptive", "game-changer", "luxury"]

[claims]
approved = [
  "4.7 stars",
  "261 verified reviews",
  "lifetime warranty",
]
"""

DIRS = ["media/source", "renders/previews", "cache", "assets/music/licensed",
        "assets/sfx", "brands"]


def init_project(root: Path, *, force: bool = False) -> list[str]:
    """Scaffold a ForwrdCut project in *root*. Returns the actions taken."""
    actions = []
    for d in DIRS:
        p = root / d
        if not p.exists():
            p.mkdir(parents=True, exist_ok=True)
            actions.append(f"created {d}/")
    cfgp = root / "config.toml"
    if cfgp.exists() and not force:
        actions.append("config.toml exists (kept — use --force to overwrite)")
    else:
        cfgp.write_text(CONFIG_TEMPLATE)
        actions.append("wrote config.toml")
    example = root / "brands" / "example.toml"
    if not example.exists():
        example.write_text(BRAND_EXAMPLE)
        actions.append("wrote brands/example.toml")
    gi = root / ".gitignore"
    if not gi.exists():
        gi.write_text("media/\ncache/\nrenders/\nassets/music/licensed/\n*.mp4\n*.mov\n")
        actions.append("wrote .gitignore (footage/renders/licensed music stay untracked)")
    return actions


def _run(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=20).stdout
    except Exception:
        return ""


def doctor(root: Path | None = None) -> tuple[list[str], int]:
    """Environment checkup. Returns (report lines, count of hard failures)."""
    lines, fails = [], 0

    def ok(msg):
        lines.append(f"  ✓ {msg}")

    def warn(msg):
        lines.append(f"  △ {msg}")

    def bad(msg):
        nonlocal fails
        fails += 1
        lines.append(f"  ✗ {msg}")

    if sys.version_info >= (3, 12):
        ok(f"python {sys.version_info.major}.{sys.version_info.minor}")
    else:
        bad(f"python {sys.version_info.major}.{sys.version_info.minor} — need 3.12+")

    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        ver = (_run(["ffmpeg", "-version"]).splitlines() or ["ffmpeg ?"])[0].split()[2] \
            if _run(["ffmpeg", "-version"]) else "?"
        ok(f"ffmpeg + ffprobe ({ver})")
        filters = _run(["ffmpeg", "-hide_banner", "-filters"])
        missing = [f for f in ("zoompan", "loudnorm", "alimiter", "xfade", "gblur",
                               "freezedetect", "sidechaincompress") if f not in filters]
        if missing:
            bad(f"ffmpeg missing filters: {', '.join(missing)} — install a full build "
                f"(brew install ffmpeg / apt install ffmpeg)")
        else:
            ok("all required ffmpeg filters present")
        encs = _run(["ffmpeg", "-hide_banner", "-encoders"])
        if "h264_videotoolbox" in encs:
            ok("hardware encoder: h264_videotoolbox")
        elif "libx264" in encs:
            warn("no VideoToolbox — using libx264 (works everywhere, slower)")
        else:
            bad("no H.264 encoder found in ffmpeg")
    else:
        bad("ffmpeg/ffprobe not on PATH — install: brew install ffmpeg (macOS) "
            "or apt install ffmpeg (Linux)")

    try:
        from .config import load_config
        cfg = load_config()
        ok(f"config.toml found ({cfg.root})")
        try:
            cfg.ensure_dirs()
            ok("project folders writable")
        except Exception as e:
            bad(f"cannot create project folders: {e}")
        kok = cfg.root / "models" / "kokoro" / "kokoro-v1.0.onnx"
        if kok.exists():
            ok("Kokoro voice model present (local neural VO)")
        else:
            warn("no Kokoro model (models/kokoro/) — VO falls back to macOS `say` or "
                 "ElevenLabs if ELEVENLABS_API_KEY is set; see docs/ENGINE.md")
        try:
            from .audio.music import scan_music
            n = len(scan_music(cfg))
            ok(f"licensed music: {n} track(s)") if n else \
                warn("no licensed music yet — drop tracks in assets/music/licensed/ "
                     "(procedural beds are the fallback)")
        except Exception:
            warn("music library scan failed (non-fatal)")
        kits = sorted((cfg.root / "brands").glob("*.toml")) if (cfg.root / "brands").exists() else []
        ok(f"brand kits: {', '.join(k.stem for k in kits)}") if kits else \
            warn("no brand kits — copy brands/example.toml to lint copy against approved claims")
    except FileNotFoundError:
        bad('no config.toml — run `forwrdcut init` in your project folder')

    try:
        import faster_whisper  # noqa: F401
        ok("faster-whisper importable (model downloads on first transcription)")
    except Exception:
        bad("faster-whisper not importable — pip install -e . (or .[voice])")

    return lines, fails
