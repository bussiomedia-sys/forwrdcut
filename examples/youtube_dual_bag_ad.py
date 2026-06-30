"""FORWRD — "Two Bags, One Standard" :30 YouTube in-stream (skippable) ad + :15
bumper cutdown. Built to the production brief + YouTube ABCD framework.

Spine = Kokoro VO (the message), reinforced by big designed CALLOUTS (one idea per
beat, white + one orange word). VO word-captions are suppressed so the callouts are
the only on-screen text (brief: overlay names the feature, VO explains it). 16:9.
Owned product-shoot b-roll (vertical macros cover-cropped to 16:9; full-bag shots
blur-padded; the 4K landscape interior used full-bleed). Brand badge in the first 5s,
star proof, generated end card. NO whoosh. Ducked bed. loudnorm ~-14 LUFS.

Two-pass: synth each VO line, measure its duration, place callouts at the right
absolute time, then render once.

Run:  .venv/bin/python make_youtube_ads.py [30|15|all]
"""
import sys, json, subprocess, hashlib
from pathlib import Path

from forwrdcut.config import load_config
from forwrdcut.strategy import edp as edpmod
from forwrdcut.render.timeline import render_timeline
from forwrdcut.render.music_gen import ensure_beds
from forwrdcut.render import graphics as G
from forwrdcut.render.captions import _load_font
from forwrdcut.audio.tts import synthesize
from PIL import Image, ImageDraw

ROOT = Path("/Users/grubbussio/AI Viral Video Editing App")
SHOOTS = Path("/Users/grubbussio/Desktop/FORWRD Video Library/04 - Product Shoots")
OUT_DIR = ROOT / "renders" / "youtube_ads"
ASSET_DIR = OUT_DIR / "assets"
VOICE = "am_michael"
FW, FH = 1920, 1080

MAN = {x["idx"]: x["path"] for x in json.loads((ROOT / "cache/owned_manifest.json").read_text())}


def clip(idx: int) -> str:
    return MAN[idx]


def wav_dur(p: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout
    return float(out.strip() or 0.0)


def vo_duration(cfg, text: str) -> float:
    """Synthesize (cached, same key as timeline) and return the VO duration."""
    key = hashlib.sha1(f"{VOICE}|{text}".encode()).hexdigest()[:16]
    vocache = cfg.cache_dir / "vo"; vocache.mkdir(parents=True, exist_ok=True)
    wav = vocache / f"{key}.wav"
    if not wav.exists():
        synthesize(text, wav, cfg=cfg, voice=VOICE)
    return wav_dur(wav)


def make_endcard(cfg) -> Path:
    """Black end card: FORWRD wordmark, orange accent, spine line, URL, approved facts."""
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    font_p = G._font_path(cfg)
    card = Image.new("RGB", (FW, FH), (10, 10, 10))
    d = ImageDraw.Draw(card)
    wm = _load_font(font_p, int(FW * 0.085), "Black")
    sub = _load_font(font_p, int(FW * 0.026), "SemiBold")
    small = _load_font(font_p, int(FW * 0.019), "Medium")

    def ctext(y, txt, font, fill):
        w = d.textlength(txt, font=font); d.text(((FW - w) / 2, y), txt, font=font, fill=fill)

    ctext(int(FH * 0.30), "FORWRD", wm, "#FFFFFF")
    rw = int(FW * 0.16)
    d.rectangle([(FW - rw) // 2, int(FH * 0.47), (FW + rw) // 2, int(FH * 0.47) + 8], fill=G._orange(cfg))
    ctext(int(FH * 0.52), "TWO BAGS. ONE STANDARD.", sub, "#FFFFFF")
    ctext(int(FH * 0.60), "forwrd.co", sub, G._orange(cfg))
    ctext(int(FH * 0.70), "LIFETIME WARRANTY  ·  SAME-DAY UTAH SHIPPING", small, "#9A9A9A")
    png = ASSET_DIR / "endcard.png"; card.save(png)
    mp4 = ASSET_DIR / "endcard.mp4"
    subprocess.run(["ffmpeg", "-y", "-loop", "1", "-i", str(png), "-t", "8",
                    "-r", "30", "-pix_fmt", "yuv420p", "-vf", f"scale={FW}:{FH}", str(mp4)],
                   capture_output=True)
    return mp4


# beat: dict(vo, src, in, reframe, callout, cpos)  |  end card uses src=endcard
def beats_30(endcard):
    return [
        dict(vo="Most pickleball bags are an afterthought. These two aren't.",
             src=clip(67), tin=2.5, reframe="cover", callout="NOT YOUR AVERAGE *BAG*", cpos="center"),
        dict(vo="Meet the Court Ranger.",
             src=clip(1), tin=0.4, reframe="blur_pad", callout="COURT *RANGER*", cpos="lower"),
        dict(vo="And the Court Caddy.",
             src=clip(40), tin=7.5, reframe="cover", callout="COURT *CADDY*", cpos="lower"),
        dict(vo="Eight forty D ballistic nylon, and Y K K zippers. Built to last.",
             src=clip(44), tin=8.5, reframe="cover", callout="840D *BALLISTIC* NYLON", cpos="lower"),
        dict(vo="A place for every paddle, every ball, everything.",
             src=clip(54), tin=54.0, reframe="cover", callout="MODULAR. *ORGANIZED.* DIALED.", cpos="lower"),
        dict(vo="Want that quality, lighter and leaner?",
             src=clip(12), tin=1.5, reframe="cover", callout=None, cpos="lower"),
        dict(vo="The Ranger opens from the front. See everything, grab anything.",
             src=clip(67), tin=18.5, reframe="cover", callout="SEE EVERYTHING. *GRAB* ANYTHING.", cpos="lower"),
        dict(vo="Same materials. Same lifetime warranty. Everyday price.",
             src=clip(34), tin=23.0, reframe="cover", callout="PREMIUM, MINUS THE *COMPROMISE*", cpos="lower"),
        dict(vo="Nine thousand five hundred players already switched.",
             src=clip(1), tin=1.0, reframe="blur_pad", callout=None, cpos="lower", stars=True),
        dict(vo="Two bags. One standard. Never settle. Forwrd dot co.",
             src=str(endcard), tin=0.0, reframe="cover", callout=None, cpos="center", endcard=True),
    ]


def beats_15(endcard):
    """:15 bumper cutdown — hook + one Caddy beat + one Ranger beat + end card.
    Reuses the :30 VO lines (cached) so nothing re-synthesizes."""
    return [
        dict(vo="Most pickleball bags are an afterthought. These two aren't.",
             src=clip(67), tin=2.5, reframe="cover", callout="NOT YOUR AVERAGE *BAG*", cpos="center"),
        dict(vo="A place for every paddle, every ball, everything.",
             src=clip(54), tin=54.0, reframe="cover", callout="MODULAR. *ORGANIZED.* DIALED.", cpos="lower"),
        dict(vo="The Ranger opens from the front. See everything, grab anything.",
             src=clip(67), tin=18.5, reframe="cover", callout="SEE EVERYTHING. *GRAB* ANYTHING.", cpos="lower"),
        dict(vo="Two bags. One standard. Never settle. Forwrd dot co.",
             src=str(endcard), tin=0.0, reframe="cover", callout=None, cpos="center", endcard=True),
    ]


def build(cfg, project, goal, beats, beds):
    # pass 1 — measure VO durations -> absolute offsets
    segs, overlays = [], []
    t = 0.0
    endcard_start = None
    for b in beats:
        dur = vo_duration(cfg, b["vo"])
        segs.append({"source": b["src"], "in": b["tin"], "out": b["tin"] + 3, "role": "vo",
                     "reframe": b["reframe"], "voiceover": b["vo"], "caption": "none"})
        if b.get("endcard"):
            endcard_start = t
        if b.get("callout"):
            overlays.append({"type": "callout", "text": b["callout"], "position": b["cpos"],
                             "start": round(t + 0.10, 2), "end": round(t + dur - 0.05, 2)})
        if b.get("stars"):
            overlays.append({"type": "stars", "rating": 4.6, "text": "9,500+ PLAYERS  ·  730+ 5-STAR",
                             "position": "upper", "start": round(t + 0.10, 2), "end": round(t + dur, 2)})
        t = round(t + dur, 2)
    # brand bug: in by ~0.3s, hold until the end card
    overlays.insert(0, {"type": "badge", "text": "FORWRD", "position": "top-right",
                        "start": 0.3, "end": round(endcard_start or t, 2)})

    return {
        "version": 1, "project": project, "platform": "youtube", "goal": goal,
        "target": {"width": FW, "height": FH, "fps": 30},
        "captions": {"mode": "auto", "style": "box-pop", "position": "lower"},
        "voice": VOICE, "mute_source": True, "auto_motion": False,
        "segments": segs, "sfx": [],
        "music": {"file": str(beds["driving"]), "gain": 0.16, "duck": True},
        "loudnorm": True, "overlays": overlays,
    }, round(t, 1)


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "30"
    cfg = load_config()
    beds = ensure_beds(cfg.root / "assets" / "music")
    endcard = make_endcard(cfg)

    if which in ("30", "all"):
        edp, total = build(cfg, "yt_twobags_30_16x9",
                           ":30 YouTube dual-bag ad — Two Bags, One Standard", beats_30(endcard), beds)
        errs = edpmod.validate(edp)
        if errs:
            print("INVALID:", errs); raise SystemExit(1)
        edpmod.save(edp, OUT_DIR / f"{edp['project']}.edp.json")
        out = OUT_DIR / f"{edp['project']}.mp4"
        print(f"[:30] measured {total}s across {len(edp['segments'])} beats, {len(edp['overlays'])} overlays")
        res = render_timeline(edp, out, cfg)
        print(f"   -> {res['output']}  ({res['resolution']}, {res['duration']:.1f}s, {res['size_bytes']//1024} KB)")

    if which in ("15", "all"):
        edp, total = build(cfg, "yt_twobags_15_16x9",
                           ":15 YouTube dual-bag bumper cutdown", beats_15(endcard), beds)
        errs = edpmod.validate(edp)
        if errs:
            print("INVALID:", errs); raise SystemExit(1)
        edpmod.save(edp, OUT_DIR / f"{edp['project']}.edp.json")
        out = OUT_DIR / f"{edp['project']}.mp4"
        print(f"[:15] measured {total}s across {len(edp['segments'])} beats, {len(edp['overlays'])} overlays")
        res = render_timeline(edp, out, cfg)
        print(f"   -> {res['output']}  ({res['resolution']}, {res['duration']:.1f}s, {res['size_bytes']//1024} KB)")
    print("DONE")
