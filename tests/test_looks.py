from forwrdcut.render.looks import build_look_graph


def test_no_look_keys_returns_none():
    assert build_look_graph({}) is None
    assert build_look_graph({"project": "x", "segments": []}) is None


def test_cinematic_sets_letterbox_and_vignette():
    g = build_look_graph({"cinematic": True})
    assert g is not None
    assert "drawbox" in g and "vignette" in g
    assert g.endswith("[vout]")


def test_glow_adds_screen_blend():
    g = build_look_graph({"glow": 0.3})
    assert "blend=all_mode=screen" in g and "gblur" in g


def test_explicit_letterbox_ratio_used():
    g = build_look_graph({"letterbox": 2.0})
    assert "iw/2.0000" in g


def test_grain_adds_noise():
    assert "noise=" in build_look_graph({"grain": True})
