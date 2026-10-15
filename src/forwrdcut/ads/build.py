"""Build a batch of paid-social ads from a short spec: shots, lines, text style, music, sizes.

A batch used to be a 300-line script. Now it is a TOML file:

    [batch]
    name = "Cute Charms 9.25"
    brand = "example"                     # brand kit: banned words, claims, product colours
    source_dir = "/path/to/clips"
    out_dir = "/path/to/review/Cute Charms 9.25"
    prefix = "pm_cute"
    ratios = ["916", "45"]
    style = "ig_box_white"                # default text style (see ads.text.STYLES)

    [tracks]
    sunnypop = { file = "/path/pm_dw_sunnypop.wav", offset = 0 }

    [[ad]]
    id = "01"
    slug = "pretzel_pushin"
    track = "sunnypop"
    beats = [["IMG_7718.MOV", 0.0, 4.5]]  # [clip, in, out] or {clip, in, out, zoom}
    text = "cute bag charms for park people"   # one line, one per beat, or [{text, start, end}]
    variants = ["the gang's all here"]    # optional: same edit, other lines (…_v2, _v3)

    # Opener tests: one shared body, versions that change only the first second and the line.
    # With `name_pattern = "{idea}_{product}_{tag}_{ratio}"` in [batch] these come out as
    # holdup_pretzel_A_916.mp4, holdup_pretzel_B_916.mp4, ...
    [[ad]]
    id = "01"
    idea = "holdup"
    product = "pretzel"
    body = [["IMG_1801.mov", 2.2, 7.2]]
    versions = [{ tag = "A", opener = ["IMG_0870.mov", 3.0, 4.0], text = "the salty one. every time." }]

Every output gets a sidecar in `_qc/` recording where each piece of text landed and when; `ads.qc` uses
it to prove the text is clear of the UI, readable, and the product is big from frame one.
"""
from __future__ import annotations

import json
import re
import subprocess
import tomllib
from pathlib import Path

from ..config import Config, load_config
from ..strategy.brand import lint_edp, load_brand
from . import framing
from .audio import mux_music
from .placements import RATIOS
from .text import render_text

FOLDER = {"916": "9x16", "45": "4x5", "11": "1x1"}
FPS = 30
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}


def still_clip(src, ratio: str, dur: float, out: Path, *, push: float = 0.06, center=None, fps: int = FPS,
               z0: float = 0.0) -> Path:
    """A photo as a clip: cover-cropped to the ratio around `center` (fractions), then a slow sub-pixel push-in
    of `push` (0.06 = 6%) over its duration. The base is rendered `push` larger than the frame, so the push
    never upsamples past the photo's own detail and never stair-steps like zoompan. `z0` starts the push
    already zoomed in, so consecutive stills of one framing (a front/back flip) can share one continuous push."""
    import cv2
    import numpy as np
    from PIL import Image, ImageOps

    ow, oh = RATIOS[ratio]
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    W0, H0 = im.size
    a = ow / oh
    cw, ch = (W0, W0 / a) if W0 / H0 < a else (H0 * a, H0)
    cx, cy = center or (0.5, 0.5)
    x0 = min(max(cx * W0 - cw / 2, 0), W0 - cw)
    y0 = min(max(cy * H0 - ch / 2, 0), H0 - ch)
    top = 1 + z0 + push
    bw, bh = int(round(ow * top)), int(round(oh * top))
    base = np.asarray(im.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize((bw, bh), Image.LANCZOS))
    n = max(1, round(dur * fps))
    proc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{ow}x{oh}",
                             "-r", str(fps), "-i", "-", "-c:v", "libx264", "-crf", "15", "-preset", "medium",
                             "-pix_fmt", "yuv420p", str(out)], stdin=subprocess.PIPE)
    for i in range(n):
        sc = (1 + z0 + push * i / max(1, n - 1)) / top
        M = np.array([[sc, 0, ow / 2 - sc * bw / 2], [0, sc, oh / 2 - sc * bh / 2]], np.float32)
        proc.stdin.write(cv2.warpAffine(base, M, (ow, oh), flags=cv2.INTER_LANCZOS4,
                                        borderMode=cv2.BORDER_REFLECT).tobytes())
    proc.stdin.close()
    proc.wait()
    return out


def load_spec(path: str | Path) -> dict:
    spec = tomllib.loads(Path(path).read_text())
    spec["_path"] = str(path)
    return spec


def _beats(ad: dict, src_dir: Path) -> list[dict]:
    out = []
    for b in ad["beats"]:
        if isinstance(b, dict):
            d = dict(b)
        else:
            d = dict(clip=b[0], **{"in": float(b[1]), "out": float(b[2])})
            if len(b) > 3 and isinstance(b[3], dict):
                d.update(b[3])
        p = Path(d["clip"])
        d["src"] = p if p.is_absolute() else src_dir / p
        out.append(d)
    return out


def _timed_text(text, durs: list[float]) -> list[dict]:
    total = sum(durs)
    if text is None:
        return []
    if isinstance(text, str):
        return [dict(text=text, start=0.0, end=total)]
    if text and isinstance(text[0], dict):
        return [dict(t, end=t.get("end", total)) for t in text]
    if len(text) != len(durs):
        raise ValueError(f"{len(text)} lines for {len(durs)} beats: give one line per beat, or timed dicts")
    out, t = [], 0.0
    for line, d in zip(text, durs):
        out.append(dict(text=line, start=t, end=t + d))
        t += d
    return out


# Meta's quality ranking penalises engagement bait (asking for comments, tags, shares, votes by
# reaction) and withheld-information clickbait. "which one's your favorite?" is a question, not bait;
# "comment your favorite" is bait.
BAIT = re.compile(r"(?i)\b(comment|tag (a|your)|tag someone|share (this|if)|like if|react with|"
                  r"type (yes|1)|drop an? \S+ (below|in the comments)|you won'?t believe|wait (for|till) the end)\b")


# Numbers that are formats, not claims: "10/10" ratings and "1." list numbering. Stripped before the
# claims check so a rating meme doesn't need a registry entry (the words around it are still checked).
IDIOMS = re.compile(r"\b\d{1,2}\s?/\s?10\b|^\s*\d{1,2}[.)]\s")


# Kit `voice.no_offers`: prices, discounts, codes and urgency (evergreen brands, fatigue-proof creative).
OFFER = re.compile(r"(?i)(\$\s?\d|\d+\s?%|\b(\d+\s?off|% off|promo|code|coupon|discount|sale|deal|"
                   r"limited|last chance|ends (soon|tonight|today)|countdown|hurry|only \d+ left|while supplies)\b)")
# Kit `voice.no_contrast_frames`: the "it's not X, it's Y" construction reads as AI copy.
CONTRAST = re.compile(r"(?i)\b(it'?s|this is|that'?s|they'?re)\s+not\b[^.!?]*[,.;:]\s*(it'?s|this is|that'?s|"
                      r"they'?re|but)\b|\bnot (just )?(a|an|the)\b[^.!?]*,\s*(it'?s|but)\b")


def copy_issues(texts: list[str], kit: dict) -> list[str]:
    edp = {"segments": [], "overlays": [{"type": "callout", "text": IDIOMS.sub(" ", t)} for t in texts]}
    issues = lint_edp(edp, kit)
    voice = kit.get("voice", {})
    issues += [f'em dash in "{t}"' for t in texts if "—" in t]
    issues += [f'engagement bait in "{t}" (Meta ranks it down)' for t in texts if BAIT.search(t)]
    if voice.get("no_offers"):
        issues += [f'offer / price / urgency wording in "{t}"' for t in texts if OFFER.search(t)]
    if voice.get("no_contrast_frames"):
        issues += [f'"it\'s not X, it\'s Y" construction in "{t}"' for t in texts if CONTRAST.search(t)]
    return issues


def expand(ad: dict, batch: dict) -> list[dict]:
    """One render job per version. An ad with `versions` becomes one job per version (opener + shared
    body, its own line); otherwise the ad itself, plus a job per text variant."""
    pattern = batch.get("name_pattern")
    jobs = []
    if ad.get("versions"):
        # versions that share one opener are a pure line test: they're meant to look alike, so QC groups them
        same_footage = len({json.dumps(v["opener"]) for v in ad["versions"]}) == 1
        for v in ad["versions"]:
            job = dict(ad, beats=[v["opener"], *ad["body"]], text=v["text"], id=f"{ad['id']}{v['tag']}",
                       group=ad["id"], tag=v["tag"])
            if same_footage:
                job["qc_group"] = ad["id"]
            job["slug"] = ad.get("slug") or f"{ad.get('idea', 'ad')}_{ad.get('product', '')}".strip("_")
            jobs.append(job)
    else:
        ad = dict(ad, slug=ad.get("slug") or f"{ad.get('idea', 'ad')}_{ad.get('product', '')}".strip("_"))
        jobs.append(dict(ad, group=ad["id"], tag=""))
        for k, v in enumerate(ad.get("variants", []), start=2):
            jobs.append(dict(ad, text=v, group=ad["id"], tag=f"v{k}", slug=f"{ad['slug']}_v{k}",
                             qc_group=ad["id"]))       # text-only variants are expected to look alike
    for j in jobs:
        j["_pattern"] = pattern
    return jobs


def out_name(job: dict, batch: dict, ratio: str) -> str:
    if job.get("_pattern"):
        return job["_pattern"].format(idea=job.get("idea", ""), product=job.get("product", ""), tag=job["tag"],
                                      ratio=ratio, id=job["id"], slug=job["slug"])
    return f"{batch.get('prefix', 'ad')}_{job['id'] if not job['tag'].startswith('v') else job['group']}_{job['slug']}_{ratio}"


def _sh(*cmd):
    subprocess.run([str(c) for c in cmd], check=True)


def render_ad(ad: dict, ratio: str, spec: dict, kit: dict, cache: Path, *, text=None, slug=None,
              name: str | None = None) -> Path:
    b = spec["batch"]
    src_dir = Path(b.get("source_dir", "."))
    beats = _beats(ad, src_dir)
    sigs = framing.signatures(kit, ad.get("products"))
    ow, oh = RATIOS[ratio]
    parts, durs, frame1_boxes = [], [], []
    fps = int(b.get("fps", FPS))
    for i, bt in enumerate(beats):
        p = cache / f"{ad['id']}_{ratio}_{i}.mp4"
        speed, hold = float(bt.get("speed", 1.0)), float(bt.get("hold", 0.0))
        src_dur = bt["out"] - bt["in"]
        dur = src_dur / speed + hold
        if Path(bt["src"]).suffix.lower() in IMAGE_EXT:           # a photo: slow push-in, no zoompan stepping
            still_clip(bt["src"], ratio, dur, p, push=float(bt.get("push", 0.06)), center=bt.get("center"),
                       fps=fps, z0=float(bt.get("z0", 0.0)))
            parts.append(p)
            durs.append(dur)
            continue
        sw, shh = framing.source_size(bt["src"])
        boxes = framing.track(bt["src"], bt["in"], bt["out"], sigs) if sigs else []
        if bt.get("center"):
            cx, cy = bt["center"]
            boxes = [(cx - 0.01, cy - 0.01, cx + 0.01, cy + 0.01)]
        x, y, w, h = framing.plan_crop(sw, shh, ratio, boxes, zoom=bt.get("zoom", 1.0))
        if i == 0 and boxes:                       # product boxes of frame one, in output pixels
            for bx in boxes[:1]:
                frame1_boxes.append(((bx[0] * sw - x) * ow / w, (bx[1] * shh - y) * oh / h,
                                     (bx[2] * sw - x) * ow / w, (bx[3] * shh - y) * oh / h))
        vf = f"crop={w}:{h}:{x}:{y}" + ("" if (w, h) == (ow, oh) else f",scale={ow}:{oh}:flags=lanczos")
        # upscaled sources (720p phone clips) get a light luma-only unsharp: edge crispness back without halos
        # or chroma artefacts
        if b.get("upscale_sharpen") and w < ow * 0.9:
            vf += ",unsharp=5:5:0.45:5:5:0.0"
        if speed != 1.0:
            vf = f"setpts=(PTS-STARTPTS)/{speed}," + vf
        if hold:
            vf += f",tpad=stop_mode=clone:stop_duration={hold}"
        _sh("ffmpeg", "-v", "error", "-y", "-ss", f"{bt['in']:.3f}", "-t", f"{src_dur:.3f}",
            "-i", bt["src"], "-vf", f"{vf},fps={fps},format=yuv420p,setsar=1", "-an",
            "-c:v", "libx264", "-crf", 15, "-preset", "medium", "-t", f"{dur:.3f}", p)
        parts.append(p)
        durs.append(dur)
    total = sum(durs)

    style = ad.get("style", b.get("style", "ig_box_white"))
    accent = kit.get("style", {}).get("highlight", "#F26F5E")
    timed = _timed_text(ad.get("text") if text is None else text, durs)
    prefer = ad.get("text_position", b.get("text_position", "top"))
    # `text_avoid = false` keeps the line in the usual spot even if the product reaches into it, so a set
    # of versions reads alike (otherwise the line hops below a product that fills the top of frame one)
    avoid = frame1_boxes if ad.get("text_avoid", True) else None
    width_frac = float(b.get("text_width", 0.84))
    first = render_text(timed[0]["text"], ratio, timed[0].get("style", style), cache=cache, avoid=avoid,
                        prefer=prefer, accent=accent, width_frac=width_frac) if timed else None
    # lines without their own `y` share the first line's height, so the text doesn't jump on a cut.
    # A `y` given as a fraction (0-1) is a share of the frame height; `dy` (px) places a line's centre
    # that far below the bottom of the first line's box, for stacked lists.
    layers = []
    for t in timed:
        y = t.get("y")
        if y is not None and y <= 1:
            y = y * oh
        if y is None and t.get("dy") is not None and first:
            y = first.box[3] + t["dy"]
        if y is None and first:
            y = (first.box[1] + first.box[3]) / 2
        layers.append(render_text(t["text"], ratio, t.get("style", style), cache=cache, y=y, accent=accent,
                                  size=t.get("size"), width_frac=width_frac))

    inputs = sum([["-i", str(p)] for p in parts + [ly.png for ly in layers]], [])
    n = len(parts)
    fc = "".join(f"[{i}:v]" for i in range(n)) + f"concat=n={n}:v=1:a=0[v0]"
    last = "v0"
    for k, (t, ly) in enumerate(zip(timed, layers)):
        nxt = f"v{k + 1}"
        fc += (f";[{last}][{n + k}:v]overlay=0:0:format=auto:"
               f"enable='between(t,{t['start']:.3f},{t['end'] - 0.001:.3f})'[{nxt}]")
        last = nxt
    mute = cache / f"{ad['id']}_{ratio}_mute.mp4"
    _sh("ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", fc, "-map", f"[{last}]",
        "-c:v", "libx264", "-crf", 17, "-preset", "slow", "-pix_fmt", "yuv420p",
        "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", mute)

    out_dir = Path(b["out_dir"]) / FOLDER[ratio]
    name = name or f"{b.get('prefix', 'ad')}_{ad['id']}_{slug or ad['slug']}_{ratio}"
    out = out_dir / f"{name}.mp4"
    tr = spec.get("tracks", {}).get(ad.get("track"))
    if tr:
        mux_music(mute, Path(tr["file"]), out, duration=total, offset=float(tr.get("offset", 0)),
                  drop_at=ad.get("drop_at"), sfx=ad.get("sfx"))
    else:
        out.parent.mkdir(parents=True, exist_ok=True)
        _sh("ffmpeg", "-v", "error", "-y", "-i", mute, "-c", "copy", "-movflags", "+faststart", out)

    side = Path(b["out_dir"]) / "_qc" / f"{name}.json"
    side.parent.mkdir(parents=True, exist_ok=True)
    side.write_text(json.dumps(dict(
        ad=ad.get("qc_group", ad["id"]), slug=slug or ad["slug"], ratio=ratio, duration=total, style=style,
        track=ad.get("track"), format=ad.get("format"), drop_at=ad.get("drop_at"),
        idea=ad.get("idea"), product=ad.get("product"), version=ad.get("tag"),
        beats=[dict(clip=str(bt["src"]), **{"in": bt["in"], "out": bt["out"]}) for bt in beats],
        texts=[dict(text=t["text"], start=t["start"], end=t["end"], lines=ly.lines, box=ly.box, style=ly.style,
                    fill=ly.fill) for t, ly in zip(timed, layers)],
        products=[p["id"] for p in framing.signatures(kit, ad.get("products"))],
    ), indent=2))
    return out


def all_texts(spec: dict) -> list[str]:
    out = []
    for ad in spec.get("ad", []):
        for t in [ad.get("text"), *ad.get("variants", []), *[v["text"] for v in ad.get("versions", [])]]:
            if isinstance(t, str):
                out.append(t)
            elif isinstance(t, list):
                out += [x["text"] if isinstance(x, dict) else x for x in t]
    return out


def build_batch(spec_path: str | Path | dict, cfg: Config | None = None, *, only: list[str] | None = None,
                variants: bool = True, log=print) -> list[Path]:
    """Build every ad in a spec (a TOML path, or the same structure as a dict)."""
    cfg = cfg or load_config()
    spec = spec_path if isinstance(spec_path, dict) else load_spec(spec_path)
    b = spec["batch"]
    kit = load_brand(cfg, b["brand"]) if b.get("brand") else {}
    issues = copy_issues(all_texts(spec), kit)
    if issues:
        raise ValueError("copy fails the brand kit:\n  " + "\n  ".join(issues))
    cache = cfg.cache_dir / "ads" / Path(b["out_dir"]).name.replace(" ", "_")
    cache.mkdir(parents=True, exist_ok=True)
    made = []
    for ad in spec.get("ad", []):
        if only and ad["id"] not in only:
            continue
        for job in expand(ad, b):
            if not variants and job["tag"].startswith("v"):
                continue
            for ratio in b.get("ratios", ["916", "45"]):
                made.append(render_ad(job, ratio, spec, kit, cache, name=out_name(job, b, ratio)))
            log(f"✓ {job['id']} {out_name(job, b, '')}")
    return made
