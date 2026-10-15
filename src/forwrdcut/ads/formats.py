"""Trend formats: current short-form formats, as recipes that turn found shots into ad specs.

Each recipe takes shots (from `ads.shots.find_windows`, or picked by hand) plus a few words, and returns
an `[[ad]]` dict for `ads.build`. Cuts land on the music's beats. The formats, what they are, and where
the evidence came from live in `TRENDS`, so a batch README can say why each ad looks the way it does and
stale formats can be retired in one place.

Research date: 2026-09-25 (trend roundups dated Aug-Sep 2026; see each entry's `source`). Trends move in
weeks: re-check anything older than about six weeks before building on it.

The original sounds behind these trends are consumer audio, not cleared for ads. Every recipe keeps the
structure and the joke and runs on music the brand owns.
"""
from __future__ import annotations

from functools import lru_cache
from ..analysis.beats import detect_beats

Shot = tuple[str, float, float]            # (clip, in, out)

TRENDS: dict[str, dict] = {
    "reasons_list": dict(
        name='"reasons to get a ___"',
        what='Deadpan caption "reasons to get a bob", then "1. bob 2. bob 3. bob" appearing on the beat, a '
             "hard cut per item.",
        source="Fat Papi 'FREAKED OUT' bob list, original 80M+ views; Epidemic Sound 2026-08-28, SocialPilot "
               "Sep 2026",
        why="The joke is that there is only one reason, and it's the product. Works for anything you can "
            "show from several angles.",
        footage="3-4 shots of one product in different places", status="current"),
    "reveal_drop": dict(
        name='"how could this day get any better" reveal',
        what="Deadpan over one lonely item with the music muffled, then the beat drops and the camera finds "
             "the whole stash.",
        source="NewEngen TikTok trends, updated 2026-09-21 ('very high' brand fit)",
        why="One charm, then all of them: sells the collection without saying 'collection'.",
        footage="one close shot of a single product, then one wide shot with all of them", status="current"),
    "rating": dict(
        name="snack rating",
        what="Quick cuts, a rating on each item, landing on the hero.",
        source="Park-creator snack reviews (Disney x TikTok creator deal coverage 2026-08-08); '10/10 habits' "
               "NewEngen 2026-09-01",
        why="Native to the park-food audience; the rating joke works because they aren't real snacks.",
        footage="one close shot per product", status="current"),
    "camera_roll": dict(
        name="camera-roll dump",
        what="A flash-cut diary of a day, cut to the beat, the product in every frame.",
        source="Lightreel IG trends 2026-09-12..19; Later Reels trends 2026-09-18",
        why="Reads as a real person's day, not an ad. Different settings in one ad are the point here.",
        footage="6-10 short shots, product visible in each", status="current"),
    "one_liner": dict(
        name="meme one-liner",
        what="A single held shot with one meme-structured line ('first in my bloodline to ___').",
        source="Ramdam IG trends 2026-09-09 ('first in my bloodline')",
        why="Cheapest format there is; the line does the work, the shot just has to be good.",
        footage="one great hold-up shot", status="current"),
    "new_season": dict(
        name="wordless new-season montage",
        what="4-6 cozy clips, no dialogue, one soft line.",
        source="NewEngen 2026-09-01 ('A New Season Had Begun'); SocialBee 2026-09-23 ('fall wishlist')",
        why="Seasonal SKUs in October.", footage="4-6 seasonal shots", status="current"),
    # need a new shoot: kept here so the shoot brief and the builder read from one list
    "bag_unpack": dict(
        name='"pov: your phone is ringing" bag unpack', status="needs shoot",
        what="Digging through an overstuffed bag, things tumbling out, fast cuts.",
        source="Trending IG sound (olyabelakoneva); Buffer, updated 2026-09-03",
        footage="park bag, charm clipped outside; poncho, sunscreen, battery pack, snacks, cooling towel"),
    "bad_dream": dict(
        name='"it was a bad dream"', status="needs shoot",
        what="The product heads for a disaster, hard cut to it tucked in bed, waking up.",
        source="COSRX sound; SocialBee 2026-08-05, still listed by Buffer and Pepper in Sep",
        footage="a charm left behind / caught in rain; then tucked under a tiny blanket; then clipped on"),
    "two_vibes": dict(
        name='"two friends, two vibes"', status="needs shoot",
        what="Two people side by side with pictures over their heads showing opposite tastes.",
        source="SocialBee 2026-09-10", footage="the sisters, each holding a different charm up"),
    # retired: don't build
    "tell_me_without": dict(name='"tell me you\'re a ___ without telling me"', status="stale",
                            source="reads as dated in 2026 roundups"),
    "pov_crutch": dict(name='"pov:" as a generic opener', status="stale",
                       source="only works tied to a specific current sound"),
    "blind_box": dict(name="Labubu / blind-box references", status="stale",
                      source="Pop Mart Americas online sales -44.6% (SCMP 2026-06)"),
}


@lru_cache(maxsize=32)
def track_beats(music: str, offset: float = 0.0, span: float = 30.0) -> tuple[float, ...]:
    """Beat times of `music` from `offset`, re-based so the first beat after the offset is near 0."""
    beats = [b - offset for b in detect_beats(music) if offset <= b <= offset + span]
    return tuple(beats)


def beat_len(music: str, offset: float = 0.0) -> float:
    b = track_beats(music, offset)
    if len(b) < 3:
        return 0.5
    import numpy as np
    return float(np.median(np.diff(b)))


def _fit(shot: Shot, dur: float) -> list:
    clip, t0, t1 = shot
    start = t0 if t1 - t0 >= dur else max(0.0, t1 - dur)
    return [str(clip), round(start, 3), round(start + dur, 3)]


def reasons_list(ad_id: str, shots: list[Shot], *, item: str, header: str, music: str, offset: float = 0.0,
                 beats_per_item: int = 2, emoji: str = "", **extra) -> dict:
    """'reasons to get a pretzel on your bag:' then '1. pretzel', '2. pretzel', ... one per cut."""
    step = beat_len(music, offset) * beats_per_item
    beats = [_fit(s, step) for s in shots]
    texts = [dict(text=header, start=0.0, end=step * len(beats))]
    for i in range(len(beats)):
        last = i == len(beats) - 1
        texts.append(dict(text=f"{i + 1}. {item}{(' ' + emoji) if last and emoji else ''}",
                          start=step * i, end=step * len(beats), dy=58 + 90 * i, style="ig_box_dark"))
    return dict(id=ad_id, format="reasons_list", beats=beats, text=texts, **extra)


def reveal_drop(ad_id: str, single: Shot, reveal: Shot, *, before: str, after: str, music: str,
                offset: float = 0.0, beats_before: int = 4, reveal_len: float = 3.5, **extra) -> dict:
    """Deadpan line over one item, music muffled; the beat drops on the cut to the whole set."""
    lead = beat_len(music, offset) * beats_before
    beats = [_fit(single, lead), _fit(reveal, reveal_len)]
    return dict(id=ad_id, format="reveal_drop", beats=beats, drop_at=round(lead, 3),
                text=[before, after], **extra)


def rating(ad_id: str, shots: list[Shot], labels: list[str], *, music: str, offset: float = 0.0,
           header: str | None = None, beats_per_item: int = 2, hero_hold: float = 1.6, **extra) -> dict:
    """One rating per cut, under an optional header that stays up; the last (hero) shot holds longer."""
    step = beat_len(music, offset) * beats_per_item
    durs = [step if i < len(shots) - 1 else step + hero_hold for i in range(len(shots))]
    beats = [_fit(s, d) for s, d in zip(shots, durs)]
    if not header:
        return dict(id=ad_id, format="rating", beats=beats, text=labels, **extra)
    total = sum(durs)
    texts, t = [dict(text=header, start=0.0, end=total)], 0.0
    for lab, d in zip(labels, durs):
        texts.append(dict(text=lab, start=t, end=t + d, dy=58, style="ig_box_dark"))
        t += d
    return dict(id=ad_id, format="rating", beats=beats, text=texts, **extra)


def camera_roll(ad_id: str, shots: list[Shot], *, line: str, music: str, offset: float = 0.0,
                beats_per_shot: int = 1, **extra) -> dict:
    """Flash cuts on every beat, one line over the whole thing."""
    step = beat_len(music, offset) * beats_per_shot
    return dict(id=ad_id, format="camera_roll", beats=[_fit(s, step) for s in shots], text=line, **extra)


def one_liner(ad_id: str, shot: Shot, *, line: str, dur: float = 5.0, **extra) -> dict:
    return dict(id=ad_id, format="one_liner", beats=[_fit(shot, dur)], text=line, **extra)
