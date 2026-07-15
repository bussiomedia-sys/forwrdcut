"""Overlay placement must respect the platform safe zones it claims to respect."""
from forwrdcut.render.graphics import _pos_xy

FW, FH = 1080, 1920          # Meta 9:16
TOP, BOTTOM = 0.14, 0.35     # Reels-ad UI: top 14%, bottom 35%


def _clears_reels_ui(position, gh):
    x, y = _pos_xy(position, 600, gh, FW, FH)
    return y >= FH * TOP and (y + gh) <= FH * (1 - BOTTOM)


def test_safe_lower_clears_reels_ad_ui():
    for gh in (80, 200, 400):
        assert _clears_reels_ui("safe_lower", gh), f"safe_lower leaks into UI at gh={gh}"


def test_plain_lower_does_not_clear_reels_ui():
    # documents *why* safe_lower exists: the default "lower" sits under the CTA button
    assert not _clears_reels_ui("lower", 200)


def test_unknown_position_falls_back_to_lower():
    assert _pos_xy("nonsense", 600, 200, FW, FH) == _pos_xy("lower", 600, 200, FW, FH)
