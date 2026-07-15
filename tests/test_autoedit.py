from forwrdcut.strategy.autoedit import beat_align_durations, enrich_for_autoedit


def test_beat_align_snaps_output_cuts_to_grid():
    # 120 bpm -> 0.5s beats. Two segments whose cuts fall just off the grid.
    segs = [{"in": 0.0, "out": 1.6}, {"in": 10.0, "out": 11.1}]
    beat_align_durations(segs, 120, max_shift=0.12)
    d0 = segs[0]["out"] - segs[0]["in"]
    d1 = segs[1]["out"] - segs[1]["in"]
    assert abs((d0) - 1.5) < 1e-6                 # first cut snapped to 1.5s
    assert abs((d0 + d1) - 2.5) < 1e-6            # cumulative second cut on the grid


def test_beat_align_skips_when_shift_too_big():
    segs = [{"in": 0.0, "out": 1.75}]             # 0.25s from any beat (>max_shift) -> untouched
    beat_align_durations(segs, 120, max_shift=0.12)
    assert segs[0]["out"] == 1.75


def test_enrich_applies_polish_layer():
    edp = {"segments": [{"source": "a.mp4", "in": 0.0, "out": 2.0, "role": "hook"}],
           "captions": {"position": "lower"}}
    out = enrich_for_autoedit(edp, "bed.wav", music_style="driving", beat_sync=False)
    assert out["emphasis"] is True
    assert out["auto_motion"] is True
    assert out["loudnorm"] is True
    assert out["sfx"] == []
    assert out["captions"]["style"] == "box-pop"
    assert out["music"]["file"] == "bed.wav" and out["music"]["duck"] is True
    seg = out["segments"][0]
    assert seg["reframe"] == "cover" and seg["caption"] == "auto"
