"""5 Meta cold-traffic ads with Kokoro voiceover storytelling.
Per-segment VO drives timing; captions sync to the voice; music ducks under it;
NO whoosh SFX; loudness-normalized to ~-14 LUFS; 9:16 + 4:5.
Run:  .venv/bin/python make_meta_ads_vo.py
"""
from pathlib import Path

from forwrdcut.config import load_config
from forwrdcut.strategy import edp as edpmod
from forwrdcut.render.timeline import render_timeline
from forwrdcut.render.music_gen import ensure_beds

C = Path("/Users/grubbussio/FORWRD/Pickleball Blanket/Court Photos")
H = Path("/Users/grubbussio/FORWRD/Pickleball Blanket/House Photos")
CL = {
    "ball": C / "dji_mimo_20260617_142520_20260617142500_1781729776443_video_glamour.MP4",
    "court": C / "dji_mimo_20260617_141316_20260617141310_1781729803920_video_glamour.MP4",
    "drape": C / "dji_mimo_20260617_141522_20260617141512_1781729793088_video_glamour.MP4",
    "glam": C / "dji_mimo_20260617_141504_20260617141456_1781729795812_video_glamour.MP4",
    "hero": C / "dji_mimo_20260617_141326_20260617141321_1781729801961_video_glamour.MP4",
    "round": H / "IMG_1127.MOV",
    "plush": H / "IMG_1128.MOV",
    "wrap": H / "IMG_1122.MOV",
    "dog": H / "IMG_1119.MOV",
    "cozy": H / "IMG_1139.MOV",
}


def build(project, voice, bed_style, beats, beds, style="bold-pop", position="center"):
    segs = [{"source": str(CL[k]), "in": s, "out": s + 3, "role": "vo",
             "reframe": "cover", "voiceover": vo} for (k, s, vo) in beats]
    return {
        "version": 1, "project": project, "platform": "meta",
        "goal": "Meta cold-traffic VO ad — The Original Pickleball Blanket",
        "target": {"width": 1080, "height": 1920, "fps": 30},
        "captions": {"mode": "auto", "style": style, "position": position},
        "voice": voice, "mute_source": True, "segments": segs, "sfx": [],
        "music": {"file": str(beds[bed_style]), "gain": 0.22, "duck": True},
        "loudnorm": True,
    }


def ads(beds):
    return [
        build("meta_vo1_origin", "am_michael", "driving", [
            ("ball", 0.3, "Nobody made a blanket for pickleball."),
            ("court", 0.5, "So we did."),
            ("round", 0.5, "Meet the original pickleball blanket."),
            ("wrap", 1.0, "Ridiculously soft, plush, and seriously oversized."),
            ("glam", 1.0, "Warm between games, and cozy long after."),
            ("cozy", 2.0, "Backed by a thirty day money back guarantee."),
            ("hero", 0.4, "Pre-order yours now and save ten dollars at forwrd dot co."),
        ], beds),
        build("meta_vo2_reveal", "af_bella", "upbeat", [
            ("court", 0.5, "Wait... is that a giant pickleball?"),
            ("drape", 0.5, "Yep. It's real."),
            ("plush", 5.0, "And it might be the comfiest blanket ever made."),
            ("dog", 2.0, "Plush enough for the whole family."),
            ("glam", 1.0, "The first blanket made for pickleball."),
            ("cozy", 2.5, "Get yours today at forwrd dot co."),
        ], beds),
        build("meta_vo3_dualuse", "af_heart", "chill", [
            ("hero", 0.5, "Freezing between games? Not anymore."),
            ("cozy", 1.0, "Warm on the sideline, and cozy on the couch."),
            ("round", 0.5, "Two sizes. Seventy two inch indoor, and sixty inch outdoor."),
            ("glam", 1.0, "Built for courts, grass, and sand."),
            ("wrap", 1.0, "Ridiculously soft, and machine washable."),
            ("ball", 0.3, "Pre-order now and save ten dollars."),
        ], beds, position="lower"),
        build("meta_vo4_gift", "af_heart", "upbeat", [
            ("round", 0.5, "The perfect gift for the pickleball obsessed."),
            ("court", 0.5, "It's a giant pickleball, that's actually a blanket."),
            ("wrap", 1.0, "Ridiculously soft, and seriously oversized."),
            ("dog", 2.0, "Send it to whoever you'd split a court with."),
            ("glam", 1.0, "The gift they'll actually use all season long."),
            ("hero", 0.4, "Order now, with thirty day returns, at forwrd dot co."),
        ], beds),
        build("meta_vo5_premium", "am_michael", "chill", [
            ("glam", 0.5, "The original pickleball blanket."),
            ("hero", 0.5, "Warm between games. Cozy long after."),
            ("round", 0.5, "Ridiculously soft. Made for players."),
            ("cozy", 2.0, "Plush, oversized, and made to last."),
            ("ball", 0.3, "Pre-order now, and save ten dollars, at forwrd dot co."),
        ], beds, style="clean-minimal", position="lower"),
    ]


FORMATS = [("9x16", 1080, 1920), ("4x5", 1080, 1350)]

if __name__ == "__main__":
    cfg = load_config()
    beds = ensure_beds(cfg.root / "assets" / "music")
    out_dir = cfg.output_dir / "meta_vo"
    for edp in ads(beds):
        for tag, w, h in FORMATS:
            e2 = {**edp, "target": {"width": w, "height": h, "fps": 30}}
            out = out_dir / f"{edp['project']}_{tag}.mp4"
            print(f"\n[{edp['project']} {tag}] voice={edp['voice']}")
            res = render_timeline(e2, out, cfg)
            print(f"   -> {out.name}  ({res['resolution']}, {res['duration']:.1f}s)")
    print("\nDONE")
