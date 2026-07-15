"""Regression guard: a voiceover segment's VIDEO must equal its VO duration — no frozen
tail past the audio, even when the source is a generated still. Uses a plain wav (no TTS
model needed). Skipped if ffmpeg/engine deps are unavailable.
"""
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

pytest.importorskip("av", reason="render deps not installed")
if shutil.which("ffmpeg") is None:
    pytest.skip("ffmpeg not available", allow_module_level=True)


def _probe(path, stream):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", stream, "-show_entries",
         "stream=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True).stdout.strip()
    return float(out or 0.0)


def test_vo_segment_video_matches_audio_on_a_still():
    from forwrdcut.config import load_config
    from forwrdcut.render.pipeline import render_vo_segment
    cfg = load_config()
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        still = d / "still.mp4"        # a generated still — the case that used to stretch
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=640x360",
                        "-t", "6", "-r", "30", "-pix_fmt", "yuv420p", str(still)],
                       capture_output=True, check=True)
        wav = d / "vo.wav"             # 2.0s tone stands in for the voiceover
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=300:duration=2.0",
                        str(wav)], capture_output=True, check=True)
        out = d / "seg.mp4"
        render_vo_segment(str(still), 0.0, wav, None, out, cfg=cfg, tw=640, th=360,
                          target_fps=30, motion="zoom_in")
        vdur, adur = _probe(out, "v:0"), _probe(out, "a:0")
        assert abs(vdur - 2.0) < 0.3, f"video ran to {vdur}s (VO is 2.0s)"
        assert abs(vdur - adur) < 0.3, f"video {vdur}s != audio {adur}s (frozen tail)"
