import numpy as np
import pytest

from forwrdcut.ads.build import _timed_text, copy_issues
from forwrdcut.ads.framing import plan_crop, product_box
from forwrdcut.ads.placements import RATIOS, safe_box, ui_boxes
from forwrdcut.ads.qc import text_contrast
from forwrdcut.ads.text import orphan_lines, render_text, wrap_balanced


def _measure(s):
    return len(s) * 10


def test_short_text_stays_on_one_line():
    assert wrap_balanced("cute bag charms", _measure, 400) == ["cute bag charms"]


def test_wrap_never_leaves_one_word_alone():
    for text in ["the cutest little park snacks for your bag",
                 "bag charms for people who love park snacks",
                 "cute bag charms for your next park day"]:
        lines = wrap_balanced(text, _measure, 300)
        assert len(lines) > 1
        assert not orphan_lines(lines), lines
        assert " ".join(lines) == text


def test_wrap_balances_lines():
    lines = wrap_balanced("which one's your favorite? they're all cute", _measure, 300)
    widths = [_measure(ln) for ln in lines]
    assert max(widths) - min(widths) <= 100


def test_safe_box_is_strictest_of_placements_sharing_a_ratio():
    x0, y0, x1, y1 = safe_box("916")
    assert (y0, 1920 - y1) == (269, 672)          # Meta: 14% top, 35% bottom
    assert all(b[2] > b[0] and b[3] > b[1] for b in ui_boxes("916"))


@pytest.mark.parametrize("ratio", list(RATIOS))
def test_rendered_text_sits_inside_safe_zone(tmp_path, ratio):
    ly = render_text("which one's your favorite? i can't pick", ratio, "ig_box_white", cache=tmp_path)
    sx0, sy0, sx1, sy1 = safe_box(ratio)
    x0, y0, x1, y1 = ly.box
    assert sx0 <= x0 and sy0 <= y0 and x1 <= sx1 and y1 <= sy1
    assert ly.png.exists()


def test_text_moves_off_the_product(tmp_path):
    _, sy0, _, _ = safe_box("916")
    product_top = (100, sy0, 980, sy0 + 300)
    ly = render_text("cute bag charms", "916", "ig_box_dark", cache=tmp_path, avoid=[product_top])
    assert ly.box[1] >= product_top[3] - 5


@pytest.mark.parametrize("src,ratio", [((1080, 1920), "45"), ((3840, 2160), "916"), ((1080, 1920), "11")])
def test_crop_has_target_aspect_and_stays_in_source(src, ratio):
    boxes = [(0.05, 0.9, 0.2, 0.99)]              # product hard in a corner
    x, y, w, h = plan_crop(*src, ratio, boxes)
    tw, th = RATIOS[ratio]
    assert abs(w / h - tw / th) < 0.01
    assert x >= 0 and y >= 0 and x + w <= src[0] and y + h <= src[1]


def test_product_box_finds_coloured_blob():
    fr = np.full((1920, 1080, 3), 128, np.uint8)
    fr[800:1200, 300:700] = (20, 110, 230)        # BGR orange
    sig = [dict(hues=[[5, 24]], sat_min=110, val_min=60)]
    b = product_box(fr, sig)
    assert b and abs(b[1] - 800 / 1920) < 0.02 and abs(b[3] - 1200 / 1920) < 0.02


def test_contrast_fails_white_on_pale_and_passes_on_dark():
    pale = np.full((200, 400, 3), 235, np.uint8)
    dark = np.full((200, 400, 3), 30, np.uint8)
    assert text_contrast(pale, (0, 0, 400, 200)) < 3
    assert text_contrast(dark, (0, 0, 400, 200)) > 7


def test_one_line_per_beat_switches_on_the_cut():
    t = _timed_text(["cute.", "cuter.", "cutest."], [2.0, 2.5, 2.0])
    assert [(x["start"], x["end"]) for x in t] == [(0.0, 2.0), (2.0, 4.5), (4.5, 6.5)]
    with pytest.raises(ValueError):
        _timed_text(["a", "b"], [1.0, 1.0, 1.0])


def test_copy_lint_catches_banned_words_and_em_dash():
    kit = {"voice": {"no_em_dash": True, "banned_words": ["adorable"]}}
    issues = copy_issues(["so adorable", "cute — really"], kit)
    assert any("adorable" in i for i in issues)
    assert any("em dash" in i for i in issues)


def test_find_windows_keeps_big_steady_runs_only():
    from forwrdcut.ads.shots import find_windows

    def smp(t, fill, motion=2.0, text=0.0):
        return dict(t=t, fill={"pretzel": fill}, motion=motion, sharp=1000.0, text=text)

    idx = [dict(file="a.mov", duration=4.0, hdr=False, width=1080, height=1920,
                samples=[smp(i * 0.25, 0.5 if i < 12 else 0.1) for i in range(16)]),
           dict(file="shaky.mov", duration=4.0, hdr=False, width=1080, height=1920,
                samples=[smp(i * 0.25, 0.6, motion=60) for i in range(16)]),
           dict(file="oldtext.mov", duration=4.0, hdr=False, width=1080, height=1920,
                samples=[smp(i * 0.25, 0.6, text=0.2) for i in range(16)])]
    hits = find_windows(idx, product="pretzel", min_fill=0.35, min_len=2.0)
    assert [h["file"] for h in hits] == ["a.mov"]
    assert hits[0]["start"] == 0.0 and abs(hits[0]["end"] - 3.0) < 0.01


def test_engagement_bait_is_flagged_but_questions_are_not():
    assert copy_issues(["which one's your favorite?"], {}) == []
    assert copy_issues(["comment your favorite below"], {})
    assert copy_issues(["tag a friend who needs this"], {})


def test_ratings_and_list_numbers_are_not_claims():
    kit = {"claims": {"approved": ["5.0 stars"]}}
    assert copy_issues(["pretzel charm: 10/10", "1. pretzel", "2. pretzel"], kit) == []
    assert copy_issues(["rated 4.9 by 900 people"], kit)


def test_reasons_list_stacks_items_under_a_header(monkeypatch):
    from forwrdcut.ads import formats as F
    monkeypatch.setattr(F, "beat_len", lambda music, offset=0.0: 0.5)
    ad = F.reasons_list("T1", [("a.mov", 0, 3), ("b.mov", 1, 4), ("c.mov", 0, 2)], item="pretzel",
                        header="reasons to get a pretzel on your bag:", music="x.wav", beats_per_item=2, emoji="🥨")
    assert [b[2] - b[1] for b in ad["beats"]] == [1.0, 1.0, 1.0]
    texts = ad["text"]
    assert texts[0]["text"].startswith("reasons") and texts[0]["end"] == 3.0
    assert [t["text"] for t in texts[1:]] == ["1. pretzel", "2. pretzel", "3. pretzel 🥨"]
    assert [t["start"] for t in texts[1:]] == [0.0, 1.0, 2.0]
    assert all(t["end"] == 3.0 for t in texts[1:])          # items accumulate, they don't replace
    assert all(s not in F.TRENDS or F.TRENDS[s]["status"] for s in F.TRENDS)


def test_reveal_drop_puts_the_drop_on_the_cut(monkeypatch):
    from forwrdcut.ads import formats as F
    monkeypatch.setattr(F, "beat_len", lambda music, offset=0.0: 0.5)
    ad = F.reveal_drop("T2", ("a.mov", 0, 5), ("b.mov", 0, 5), before="one", after="all", music="x", beats_before=4)
    assert ad["drop_at"] == 2.0 and ad["beats"][0][2] - ad["beats"][0][1] == 2.0


def test_offer_and_contrast_lines_fail_when_the_kit_says_so():
    kit = {"voice": {"no_offers": True, "no_contrast_frames": True}}
    for bad in ["20% off this week", "limited drop", "last chance for spooky season", "$29 and worth it",
                "it's not a keychain, it's a personality", "not just a charm, it's a mood"]:
        assert copy_issues([bad], kit), bad
    for ok in ["the salty one. every time.", "bigger than you'd think.", "embroidered, not printed."]:
        assert copy_issues([ok], kit) == [], ok


def test_versions_share_a_body_and_change_only_opener_and_line():
    from forwrdcut.ads.build import expand, out_name
    ad = dict(id="01", idea="holdup", product="pretzel", track="t", body=[["body.mov", 2, 7]],
              versions=[dict(tag="A", opener=["a.mov", 3, 4], text="one"),
                        dict(tag="B", opener=["b.mov", 0, 1], text="two")])
    batch = {"name_pattern": "{idea}_{product}_{tag}_{ratio}"}
    jobs = expand(ad, batch)
    assert [j["beats"][1:] for j in jobs] == [[["body.mov", 2, 7]]] * 2
    assert [j["beats"][0][0] for j in jobs] == ["a.mov", "b.mov"]
    assert [out_name(j, batch, "916") for j in jobs] == ["holdup_pretzel_A_916", "holdup_pretzel_B_916"]


def test_still_clip_pushes_in_and_keeps_frame_size(tmp_path):
    import subprocess

    import numpy as np
    from PIL import Image

    from forwrdcut.ads.build import still_clip
    img = np.zeros((1000, 800, 3), np.uint8)
    img[450:550, 350:450] = 255                          # a white square in the middle
    Image.fromarray(img).save(tmp_path / "p.png")
    out = still_clip(tmp_path / "p.png", "45", 1.0, tmp_path / "s.mp4", push=0.2, fps=10)
    info = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames", "-show_entries",
                           "stream=width,height,nb_read_frames", "-of", "csv=p=0", str(out)],
                          capture_output=True, text=True).stdout.strip()
    assert info == "1080,1350,10"
    import cv2
    cap = cv2.VideoCapture(str(out))
    first = cap.read()[1][..., 0] > 128
    for _ in range(9):
        last = cap.read()[1][..., 0] > 128
    assert last.sum() > first.sum() * 1.3              # the square grows: it's a push-in, not a hold


def test_offer_lint_still_allows_drop_language():
    kit = {"voice": {"no_offers": True, "no_contrast_frames": True}}
    for ok in ["the christmas drop just landed.", "four new charms. just landed.", "out now ✦"]:
        assert copy_issues([ok], kit) == [], ok
