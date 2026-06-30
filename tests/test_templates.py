from forwrdcut.strategy.templates import (
    beat_slideshow, feature_showcase, photo_slideshow, _slot_window, TEMPLATES,
)


def test_registry():
    assert set(TEMPLATES) == {"beat_slideshow", "feature_showcase", "photo_slideshow"}


def test_photo_slideshow_dwell_and_titles():
    photos = [{"path": f"{i}.jpg"} for i in range(3)]
    edp = photo_slideshow(photos, bpm=120, target=(1080, 1920), music_file="b.wav",
                          beats_per_photo=4, titles=["THE *BIG* BAG", "BUILT FOR *TRAVEL*", ""])
    assert len(edp["segments"]) == 3
    assert all(round(s["out"] - s["in"], 3) == 2.0 for s in edp["segments"])  # 4 beats @120bpm
    assert len(edp["overlays"]) == 2                 # blank third title -> no overlay
    assert edp["segments"][0]["motion"] == "zoom_in" and edp["segments"][1]["motion"] == "zoom_out"


def test_slot_window_centers_and_clamps():
    assert _slot_window(10.0, 2.0) == (4.0, 6.0)     # centered 2s window of a 10s clip
    assert _slot_window(1.0, 2.0) == (0.0, 2.0)      # clip shorter than slot -> from 0
    assert _slot_window(None, 2.0) == (0.0, 2.0)


def test_beat_slideshow_is_beat_timed():
    clips = [{"path": f"{i}.mp4", "duration": 10.0} for i in range(4)]
    edp = beat_slideshow(clips, bpm=120, target=(1080, 1920), beats_per_clip=2,
                         music_file="bed.wav")
    assert len(edp["segments"]) == 4
    # 120 bpm, 2 beats -> 1.0s slots
    durs = [round(s["out"] - s["in"], 3) for s in edp["segments"]]
    assert all(d == 1.0 for d in durs)
    assert edp["music"]["file"] == "bed.wav"
    assert edp["segments"][0]["motion"] == "zoom_in" and edp["segments"][1]["motion"] == "zoom_out"


def test_feature_showcase_callouts_align_to_beats():
    clips = [{"path": f"{i}.mp4", "duration": 8.0} for i in range(3)]
    edp = feature_showcase(clips, ["NOT YOUR AVERAGE *BAG*", "BUILT *DIFFERENT*", "SHOP *NOW*"],
                           target=(1920, 1080), music_file="bed.wav", seconds_per=2.5)
    assert len(edp["segments"]) == 3 and len(edp["overlays"]) == 3
    assert edp["overlays"][0]["start"] == 0.1
    assert edp["overlays"][1]["start"] == 2.6     # second beat at 2.5s + 0.1
    assert edp["segments"][0]["motion"] == "punch"


def test_cinematic_look_merges_in():
    clips = [{"path": "a.mp4", "duration": 5.0}]
    edp = beat_slideshow(clips, bpm=120, target=(1080, 1920), music_file="b.wav",
                         look={"cinematic": True})
    assert edp.get("cinematic") is True
