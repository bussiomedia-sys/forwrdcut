import pytest

from forwrdcut.strategy.briefs import BRIEFS, get_brief, render_brief


def test_all_briefs_are_complete():
    required = {"name", "spec", "sound", "hook", "structure", "safe_zones", "do", "dont", "edp"}
    for key, b in BRIEFS.items():
        missing = required - set(b)
        assert not missing, f"{key} missing {missing}"
        assert b["structure"] and b["do"] and b["dont"]


def test_aliases_resolve():
    assert get_brief("meta")["key"] == "meta_ad"
    assert get_brief("YouTube")["key"] == "youtube_ad"
    assert get_brief("tiktok")["key"] == "tiktok_organic"


def test_unknown_platform_raises_with_options():
    with pytest.raises(KeyError) as e:
        get_brief("myspace")
    assert "meta_ad" in str(e.value)


def test_render_brief_is_readable():
    out = render_brief("meta_ad")
    assert "safe" in out and "structure" in out and "✓" in out and "✗" in out


def test_meta_ad_brief_carries_the_reels_safe_zone():
    edp = get_brief("meta_ad")["edp"]
    assert edp["captions"]["safe_bottom_frac"] == 0.35


def test_bumper_is_six_seconds_hard():
    assert "6s" in get_brief("bumper")["spec"] or "6 s" in get_brief("bumper")["spec"]
