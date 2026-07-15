"""A timeline that mixes still images with video clips must keep every beat.

Regression: JPEG stills decode full-range, so their segments encoded as `yuvj420p` while
video-sourced segments stayed `yuv420p`. `concat -c copy` across that mismatch exits 0 but
silently drops beats and holds a single frame in their place. The engine's own QC only saw
it as "frozen video".
"""
import subprocess

import pytest

from forwrdcut.config import load_config
from forwrdcut.render.timeline import _parts_are_concat_compatible, render_timeline


def _probe(path, entries, stream="v:0"):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", stream, "-show_entries",
         f"stream={entries}", "-of", "compact=p=0:nk=1", str(path)],
        capture_output=True, text=True).stdout.strip()
    return out


def _mean_color(video, at):
    """Average RGB of one frame, via a 1x1 downscale."""
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(video), "-ss", str(at), "-frames:v", "1",
         "-vf", "scale=1:1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True).stdout
    return tuple(raw[:3])


@pytest.fixture
def assets(tmp_path):
    """A red JPEG still and a green video, both 320x320."""
    still = tmp_path / "red.jpg"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                    "-i", "color=c=red:s=320x320:d=1", "-frames:v", "1", str(still)],
                   check=True)
    clip = tmp_path / "green.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                    "-i", "color=c=green:s=320x320:d=2:r=30", "-pix_fmt", "yuv420p",
                    "-c:v", "libx264", str(clip)], check=True)
    return still, clip


def _edp(still, clip, tmp_path):
    return {
        "version": 1, "project": "mixed", "platform": "meta",
        "target": {"width": 320, "height": 320, "fps": 30},
        "mute_source": True, "auto_motion": False, "transition": "cut",
        "segments": [
            {"source": str(still), "in": 0.0, "out": 1.0, "role": "seg", "caption": "none"},
            {"source": str(clip), "in": 0.0, "out": 1.0, "role": "seg", "caption": "none"},
            {"source": str(still), "in": 0.0, "out": 1.0, "role": "seg", "caption": "none"},
        ],
        "overlays": [], "sfx": [], "loudnorm": False,
    }


def test_still_segments_encode_limited_range(assets, tmp_path):
    """The still must not come out of the encoder tagged full-range."""
    still, clip = assets
    cfg = load_config()
    cfg.data.setdefault("render", {})["segment_cache"] = False
    cfg.data.setdefault("grade", {})["enabled"] = False
    out = tmp_path / "out.mp4"
    render_timeline(_edp(still, clip, tmp_path), out, cfg)
    assert _probe(out, "pix_fmt") == "yuv420p"


def test_mixed_still_and_video_keeps_every_beat(assets, tmp_path):
    """red still -> green clip -> red still. All three must survive the concat."""
    still, clip = assets
    cfg = load_config()
    cfg.data.setdefault("render", {})["segment_cache"] = False
    cfg.data.setdefault("grade", {})["enabled"] = False
    out = tmp_path / "out.mp4"
    render_timeline(_edp(still, clip, tmp_path), out, cfg)

    dur = float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
         str(out)], capture_output=True, text=True).stdout.strip())
    assert dur == pytest.approx(3.0, abs=0.2), f"expected ~3s, got {dur}"

    r1, g1, _ = _mean_color(out, 0.5)     # beat 1: red
    r2, g2, _ = _mean_color(out, 1.5)     # beat 2: green
    r3, g3, _ = _mean_color(out, 2.5)     # beat 3: red
    assert r1 > g1, f"beat 1 should be red, got {(r1, g1)}"
    assert g2 > r2, f"beat 2 should be green, got {(r2, g2)} (the dropped-beat bug)"
    assert r3 > g3, f"beat 3 should be red, got {(r3, g3)}"


def test_overlays_plus_loudnorm_keep_every_beat(assets, tmp_path):
    """Overlays + loudnorm must not drop beats.

    Regression: folding the loudnorm audio filter into the same filter_complex as the
    chained-overlay video graph (with the hardware encoder and `-shortest`) starved the
    overlay framesync and silently dropped and held whole video beats. loudnorm now runs
    as a separate audio-only pass.
    """
    still, clip = assets
    cfg = load_config()
    cfg.data.setdefault("render", {})["segment_cache"] = False
    cfg.data.setdefault("grade", {})["enabled"] = False
    out = tmp_path / "out.mp4"
    edp = _edp(still, clip, tmp_path)
    edp["loudnorm"] = True
    edp["overlays"] = [
        {"type": "callout", "text": "ONE", "position": "upper", "start": 0.1, "end": 0.9},
        {"type": "callout", "text": "TWO", "position": "upper", "start": 1.1, "end": 1.9},
        {"type": "callout", "text": "THREE", "position": "upper", "start": 2.1, "end": 2.9},
    ]
    render_timeline(edp, out, cfg)

    r2, g2, _ = _mean_color(out, 1.5)     # middle beat must still be the green video
    assert g2 > r2, f"middle beat lost under overlays+loudnorm, got {(r2, g2)}"
    r1, g1, _ = _mean_color(out, 0.5)
    r3, g3, _ = _mean_color(out, 2.5)
    assert r1 > g1 and r3 > g3, "outer still beats corrupted"


def test_voiceover_on_a_still_image_has_video(assets, tmp_path):
    """A VO beat sourced from a still image must render a real video track.

    Regression: render_vo_segment used `-ss/-t` (a video seek) on image sources, yielding a
    single frame and an audio-only segment. Still sources must loop for the VO length.
    """
    still, _ = assets
    cfg = load_config()
    cfg.data.setdefault("render", {})["segment_cache"] = False
    cfg.data.setdefault("grade", {})["enabled"] = False
    edp = {
        "version": 1, "project": "vo_still", "platform": "meta",
        "target": {"width": 320, "height": 320, "fps": 30},
        "mute_source": True, "auto_motion": False,
        "segments": [{"source": str(still), "in": 0.0, "out": 6.0, "role": "vo",
                      "voiceover": "Red red red.", "caption": "none"}],
        "overlays": [], "sfx": [], "loudnorm": False,
    }
    out = tmp_path / "out.mp4"
    render_timeline(edp, out, cfg)
    vcodec = _probe(out, "codec_type", stream="v:0")
    assert vcodec == "video", "VO-over-still produced no video stream"
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                "-of", "csv=p=0", str(out)], capture_output=True,
                               text=True).stdout.strip())
    assert dur > 0.4, f"VO-over-still too short: {dur}s"
    r, g, b = _mean_color(out, dur / 2)
    assert r > g and r > b, f"still content lost, got {(r, g, b)}"


def test_concat_compatibility_detects_pix_fmt_mismatch(assets, tmp_path):
    """The guard must reject a mismatched pair rather than trust `-c copy`."""
    still, clip = assets
    full = tmp_path / "full.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-t", "1", "-i", str(still),
                    "-c:v", "libx264", "-pix_fmt", "yuvj420p", "-r", "30", str(full)], check=True)
    lim = tmp_path / "lim.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(clip),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", str(lim)], check=True)
    assert _parts_are_concat_compatible([full, full]) is True
    assert _parts_are_concat_compatible([full, lim]) is False
