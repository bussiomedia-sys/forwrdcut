from forwrdcut.analysis.library import _tokens, best_window, score_clip


def _w(word, start, end):
    return {"word": word, "start": start, "end": end}


def test_tokens_drop_stopwords():
    assert _tokens("the clamshell opens with the paddles") == ["clamshell", "opens", "paddles"]


def test_best_window_finds_the_moment():
    words = ([_w(x, i * 0.4, i * 0.4 + 0.3) for i, x in enumerate(
        "so today we are looking at this bag".split())] +
        [_w(x, 10 + i * 0.4, 10 + i * 0.4 + 0.3) for i, x in enumerate(
            "the clamshell opens and your paddles sit right inside".split())])
    hit = best_window(words, ["clamshell", "paddles"])
    assert hit is not None
    assert 9.5 <= hit["start"] <= 10.5          # points at the right moment, not the intro
    assert set(hit["matched"]) == {"clamshell", "paddles"}


def test_best_window_none_when_no_match():
    words = [_w("hello", 0, 0.3), _w("world", 0.4, 0.7)]
    assert best_window(words, ["clamshell"]) is None
    assert best_window([], ["x"]) is None


def test_score_transcript_beats_filename():
    q = _tokens("fence hooks")
    t_match = score_clip(q, {"fence", "hooks", "bag"}, "video1.mp4")
    f_match = score_clip(q, {"bag"}, "fence-hooks-demo.mp4")
    assert t_match > f_match > 0
    assert score_clip(q, {"bag"}, "video1.mp4") == 0
