import subprocess
import tempfile
from pathlib import Path

import pytest

from forwrdcut.analysis.qc import evaluate, qc_render
from forwrdcut.config import load_config


def test_evaluate_flags_stream_mismatch_and_clipping():
    issues = evaluate(30.0, 16.0, -14.0, -0.2, [], False, 30.0)
    assert any("stream mismatch" in i for i in issues)
    assert any("clipping" in i for i in issues)


def test_evaluate_endcard_freeze_is_allowed_mid_freeze_is_not():
    end_freeze = [{"start": 27.0, "duration": 3.0}]         # runs to the end: end card
    assert evaluate(30.0, 30.0, -14.0, -2.0, end_freeze, False, 30.0) == []
    mid_freeze = [{"start": 10.0, "duration": 3.0}]
    assert any("frozen video" in i
               for i in evaluate(30.0, 30.0, -14.0, -2.0, mid_freeze, False, 30.0))


def test_evaluate_loudness_rules():
    assert any("loudness" in i for i in evaluate(10, 10, -25.0, -2.0, [], False, 10))
    assert evaluate(10, 10, -25.0, -2.0, [], False, 10, loudnorm_expected=False) == []
    assert any("black" in i for i in evaluate(10, 10, -14.0, -2.0, [], True, 10))


def _have_ffmpeg() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True)
        return True
    except OSError:
        return False


@pytest.mark.skipif(not _have_ffmpeg(), reason="ffmpeg not available")
def test_qc_render_catches_frozen_tail_on_real_file():
    cfg = load_config()
    with tempfile.TemporaryDirectory() as d:
        bad = Path(d) / "bad.mp4"
        # 2s of moving video + audio, then video padded (frozen clone) to 6s: audio 2s vs video 6s
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=30:duration=2",
             "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
             "-vf", "tpad=stop_mode=clone:stop_duration=4",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(bad)],
            capture_output=True, check=True)
        report = qc_render(cfg, bad, sheet=False, loudnorm_expected=False)
        assert not report["ok"]
        assert any("stream mismatch" in i for i in report["issues"])
        assert report["freezes"], "the 4s frozen tail should be detected"
        assert Path(str(bad) + ".qc.json").exists()
