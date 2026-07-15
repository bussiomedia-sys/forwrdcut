from forwrdcut.audio.music import mood_of, pick_from


def test_mood_from_filename_tokens():
    assert mood_of("FORWRD_upbeat_summer_128bpm.mp3") == "upbeat"
    assert mood_of("Epic-Trailer-Hit.wav") == "cinematic"
    assert mood_of("lofi_study_beats.m4a") == "chill"
    assert mood_of("chillwave-mix.mp3") == "chill"          # substring fallback
    assert mood_of("track01.wav") is None


def test_pick_prefers_exact_mood_then_untagged():
    tracks = [
        {"path": "a", "duration": 60, "mood": "chill"},
        {"path": "b", "duration": 90, "mood": None},
        {"path": "c", "duration": 45, "mood": "upbeat"},
    ]
    assert pick_from(tracks, mood="upbeat")["path"] == "c"   # exact beats longer untagged
    assert pick_from(tracks, mood="driving")["path"] == "b"  # no exact -> untagged
    assert pick_from(tracks)["path"] == "b"                  # no mood -> longest


def test_pick_respects_min_duration_and_empty():
    tracks = [{"path": "a", "duration": 10, "mood": "upbeat"}]
    assert pick_from(tracks, mood="upbeat", min_duration=30) is None
    assert pick_from([], mood="upbeat") is None
