import tempfile
from pathlib import Path

from forwrdcut.analysis.beats import (
    beat_grid, downbeats, snap_to_beats, beats_for_bed, estimate_tempo, detect_beats,
)
from forwrdcut.render.music_gen import generate_bed, STYLES


def test_beat_grid_exact():
    g = beat_grid(120, 4.0)            # 120 bpm → 0.5s spacing
    assert g[:4] == [0.0, 0.5, 1.0, 1.5]
    assert g[-1] <= 4.0 + 1e-6
    assert beat_grid(0, 4.0) == []
    assert beat_grid(120, 0) == []


def test_subdivision_and_downbeats():
    assert beat_grid(120, 1.0, subdivision=2)[:3] == [0.0, 0.25, 0.5]
    assert downbeats(120, 4.0)[:2] == [0.0, 2.0]   # one downbeat per 4 beats (2s at 120bpm)


def test_snap_to_beats_tolerance():
    beats = [0.0, 0.5, 1.0, 1.5]
    # 0.54 snaps to 0.5; 0.8 is >0.12 from any beat → preserved
    assert snap_to_beats([0.54, 0.8, 1.02], beats, max_shift=0.12) == [0.5, 0.8, 1.0]
    assert snap_to_beats([0.3], []) == [0.3]       # no beats → identity


def test_beats_for_bed_matches_style_bpm():
    g = beats_for_bed("driving", 2.0)
    assert g[0] == 0.0 and abs(g[1] - 60.0 / STYLES["driving"]["bpm"]) < 1e-6


def test_detect_on_generated_bed():
    with tempfile.TemporaryDirectory() as d:
        bed = generate_bed(Path(d) / "b.wav", duration=8.0, style="driving")  # 120 bpm
        bpm = estimate_tempo(bed)
        assert 55 <= bpm <= 250                      # detected (allow octave error)
        beats = detect_beats(bed, 8.0)
        assert len(beats) >= 6                        # produced a usable grid
        spacing = beats[1] - beats[0]
        assert 0.2 <= spacing <= 1.1                  # plausible beat period
