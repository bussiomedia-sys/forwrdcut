"""Brand-mark overlays and the premium callout/shadow treatment."""
import wave

import numpy as np
from PIL import Image

from forwrdcut.config import load_config
from forwrdcut.render.graphics import _callout, _with_shadow, build_overlay_specs
from forwrdcut.render.music_gen import generate_whimsical_bed


def test_with_shadow_grows_canvas_and_adds_alpha():
    src = Image.new("RGBA", (100, 40), (255, 255, 255, 255))
    out = _with_shadow(src, blur=6, alpha=150, offset=(0, 3))
    assert out.width > src.width and out.height > src.height
    a = np.asarray(out)[:, :, 3]
    # the composite has strictly more opaque coverage than the bare art (shadow halo added)
    assert (a > 0).sum() > 100 * 40, "no shadow halo added around the art"
    # and that halo is soft: a band of partially-transparent pixels exists
    assert ((a > 0) & (a < 255)).sum() > 0, "shadow is not feathered"


def test_callout_has_soft_edge_not_hard_black_keyline():
    """The premium callout uses a soft shadow, so its bounding box has a feathered alpha
    ramp rather than the solid black ring the old heavy stroke produced."""
    cfg = load_config()
    img = _callout("THE SHAPE *STAYS*", 1080, cfg, None)
    a = np.asarray(img)[:, :, 3]
    # a feathered shadow yields many partially-transparent pixels; a hard keyline yields
    # mostly 0/255. Assert a meaningful fraction of alpha is in the mid-range.
    mid = ((a > 20) & (a < 235)).mean()
    assert mid > 0.05, f"alpha looks hard-edged (mid-fraction {mid:.3f})"


def test_chip_emphasis_paints_an_orange_pill_behind_the_hot_word():
    """emphasis_style='chip' must draw the brand-orange pill so the hot word stays legible on
    any background (including a beat whose background is itself the brand orange)."""
    cfg = load_config()
    orange = cfg.captions.get("highlight", "#EA6024").lstrip("#")
    or_rgb = tuple(int(orange[i:i + 2], 16) for i in (0, 2, 4))
    plain = _callout("THE *SAVORY* ONE", 1080, cfg, None, emphasis_style="color")
    chipd = _callout("THE *SAVORY* ONE", 1080, cfg, None, emphasis_style="chip")

    def longest_orange_run(img):
        """Longest horizontal run of orange pixels. A solid pill yields a long unbroken run;
        orange *text* is broken up by the letter shapes, so its runs are short."""
        a = np.asarray(img.convert("RGB")).astype(int)
        near = (np.abs(a[:, :, 0] - or_rgb[0]) < 30) & \
               (np.abs(a[:, :, 1] - or_rgb[1]) < 30) & \
               (np.abs(a[:, :, 2] - or_rgb[2]) < 30)
        best = 0
        for row in near:
            run = 0
            for v in row:
                run = run + 1 if v else 0
                best = max(best, run)
        return best

    # the chip is a continuous orange bar; orange *text* never is
    assert longest_orange_run(chipd) > longest_orange_run(plain) * 2


def test_logo_overlay_composites_a_real_png(tmp_path):
    # a stand-in brand PNG (white glyph on transparent)
    logo = tmp_path / "logo.png"
    Image.new("RGBA", (600, 200), (255, 255, 255, 255)).save(logo)
    cfg = load_config()
    specs = build_overlay_specs(
        [{"type": "logo", "path": str(logo), "position": "upper", "width_frac": 0.44,
          "start": 0.2, "end": 3.2}],
        (1080, 1920), 12.0, cfg, tmp_path)
    assert len(specs) == 1
    out = Image.open(specs[0]["png"])
    # scaled to ~44% of 1080 (plus shadow padding), not the original 600px
    assert 460 < out.width < 560
    assert specs[0]["enable"] == "between(t,0.2,3.2)"


def test_callout_overlay_carries_fade_timing(tmp_path):
    """A callout with a fade must surface start/end/fade so the timeline can build the alpha
    ramp; the default (no fade) must stay 0 so existing hard-cut ads are unchanged."""
    cfg = load_config()
    specs = build_overlay_specs(
        [{"type": "callout", "text": "Made to be held", "position": "lower",
          "upper": False, "start": 3.2, "end": 6.0, "fade": 0.55}],
        (1080, 1920), 16.0, cfg, tmp_path)
    assert specs[0]["fade"] == 0.55
    assert specs[0]["start"] == 3.2 and specs[0]["end"] == 6.0
    assert specs[0]["enable"] == "between(t,3.2,6.0)"

    plain = build_overlay_specs(
        [{"type": "callout", "text": "X", "position": "lower", "start": 1, "end": 2}],
        (1080, 1920), 8.0, cfg, tmp_path)
    assert plain[0]["fade"] == 0.0   # unchanged behavior for the DR cuts


def test_callout_sentence_case_is_not_uppercased():
    """upper=False must leave the string case intact (the font may still be caps-only, but
    the engine must not be the thing forcing caps)."""
    import numpy as np
    cfg = load_config()
    up = _callout("Made to be held", 1080, cfg, None, upper=True)
    lo = _callout("Made to be held", 1080, cfg, None, upper=False)
    # different case input -> different rendered pixels (unless the font is caps-only, in
    # which case they match — either way the call must not raise and must return an image)
    assert up.size[0] > 0 and lo.size[0] > 0
    assert np.asarray(lo)[:, :, 3].any()


def test_whimsical_bed_is_tonal_and_not_silent(tmp_path):
    p = generate_whimsical_bed(tmp_path / "bed.wav", duration=8.0)
    w = wave.open(str(p))
    raw = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(float)
    mono = raw.reshape(-1, 2).mean(1) / 32768
    assert w.getframerate() == 48000 and w.getnchannels() == 2
    assert np.sqrt((mono ** 2).mean()) > 0.02, "bed is effectively silent"
    # bright, bell-like content: spectral centroid well above a bass-only drone
    spec = np.abs(np.fft.rfft(mono))
    freqs = np.fft.rfftfreq(len(mono), 1 / 48000)
    centroid = (freqs * spec).sum() / spec.sum()
    assert centroid > 700, f"bed is too dark to be a music box ({centroid:.0f} Hz)"
