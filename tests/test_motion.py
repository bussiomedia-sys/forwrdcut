from forwrdcut.render.pipeline import _motion_chain


def test_no_motion_no_pulses_is_empty():
    assert _motion_chain(None, 1080, 1920, 30) == ""


def test_eased_zoom_uses_curve_when_nframes_known():
    fc = _motion_chain("zoom_in", 1080, 1920, 30, nframes=90)
    assert "zoompan" in fc
    assert "pow(" in fc            # cubic ease, not a linear creep
    assert "clip(on/90" in fc      # normalized over the segment length


def test_linear_fallback_without_nframes():
    fc = _motion_chain("zoom_in", 1080, 1920, 30)
    assert "zoompan" in fc and "0.00060*on" in fc   # legacy linear path


def test_emphasis_pulses_add_bumps():
    fc = _motion_chain(None, 1080, 1920, 30, pulses=[0.5, 1.5], nframes=90)
    assert fc.count("exp(") == 2   # one gaussian bump per emphasis time


def test_shake_jitters_xy_and_adds_headroom():
    fc = _motion_chain(None, 1080, 1920, 30, shake=0.5, nframes=90)
    assert "sin(on" in fc and "cos(on" in fc   # x/y oscillation
    assert "0.06" in fc                          # crop headroom so the shake has room


def test_shake_alone_is_not_empty():
    assert _motion_chain(None, 1080, 1920, 30, shake=0.3) != ""
