from forwrdcut.analysis.emphasis import score_word, find_emphasis, emphasis_pulses


def _w(word, start, end):
    return {"word": word, "start": start, "end": end}


def test_stopwords_never_emphasised():
    assert score_word(None, _w("the", 0.0, 0.1)) < 0
    assert score_word(None, _w("and", 0.0, 0.1)) < 0


def test_strong_and_long_words_score():
    assert score_word(None, _w("ballistic", 0.0, 0.4)) >= 1.4     # long + drawn-out
    assert score_word(None, _w("everything!", 1.0, 1.4)) >= 1.4   # strong punctuation


def test_find_emphasis_spacing_and_order():
    words = [
        _w("most", 0.0, 0.2), _w("weekender", 0.3, 0.75), _w("bags", 0.8, 1.0),
        _w("are", 1.0, 1.1), _w("an", 1.1, 1.2), _w("afterthought.", 1.4, 1.9),
        _w("these", 2.4, 2.6), _w("two", 2.6, 2.8), _w("aren't!", 2.9, 3.3),
    ]
    em = find_emphasis(words, min_spacing=0.7)
    times = [e["time"] for e in em]
    assert times == sorted(times)                    # chronological
    assert all(times[i + 1] - times[i] >= 0.7 for i in range(len(times) - 1))
    assert any(e["word"].startswith("afterthought") for e in em)


def test_emphasis_pulses_relative_to_segment():
    words = [_w("ballistic", 5.0, 5.4), _w("nylon", 5.5, 5.9)]
    pulses = emphasis_pulses(words, 4.0, 7.0, threshold=1.0)
    assert pulses and all(0.0 <= p <= 3.0 for p in pulses)   # offset into the segment
    assert emphasis_pulses(words, 0.0, 3.0, threshold=1.0) == []  # outside the window
