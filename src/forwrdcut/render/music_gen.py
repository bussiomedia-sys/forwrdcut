"""Procedural royalty-free music bed generator (numpy synth).

100% generated locally → no licensing/copyright risk, safe for paid ads. Renders
a short, loopable arrangement (pad chords + bass + arp + kick/hi-hat/snare) over
an uplifting I-V-vi-IV progression. Styles vary tempo/instrumentation.

Output: 48kHz stereo 16-bit WAV.
"""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SR = 48000

# I-V-vi-IV voiced near C4 for smooth voice-leading; bass roots below.
CHORDS = [[60, 64, 67], [62, 67, 71], [60, 64, 69], [60, 65, 69]]
BASSES = [36, 43, 45, 41]

STYLES = {
    "upbeat":  {"bpm": 124, "arp": True,  "arp_wave": "tri", "snare": True,  "hat": True,  "pad": 0.16, "bass": 0.5, "arp_v": 0.22, "kick": 0.9},
    "driving": {"bpm": 120, "arp": True,  "arp_wave": "saw", "snare": True,  "hat": True,  "pad": 0.13, "bass": 0.6, "arp_v": 0.20, "kick": 1.0},
    "chill":   {"bpm": 92,  "arp": False, "arp_wave": "tri", "snare": False, "hat": False, "pad": 0.22, "bass": 0.42, "arp_v": 0.0, "kick": 0.6},
}


def _midi_freq(m: int) -> float:
    return 440.0 * (2 ** ((m - 69) / 12.0))


def _osc(freq: float, n: int, wave_type: str = "sine") -> np.ndarray:
    t = np.arange(n) / SR
    p = freq * t
    if wave_type == "tri":
        return 2 * np.abs(2 * (p % 1) - 1) - 1
    if wave_type == "saw":
        return 2 * (p % 1) - 1
    return np.sin(2 * np.pi * p)


def _place(buf: np.ndarray, start: int, sig: np.ndarray) -> None:
    end = min(len(buf), start + len(sig))
    if start < end:
        buf[start:end] += sig[:end - start]


def _kick(vel: float) -> np.ndarray:
    n = int(0.18 * SR)
    t = np.arange(n) / SR
    f = 45 + 80 * np.exp(-t / 0.025)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.11)
    return x * vel


def _hat() -> np.ndarray:
    n = int(0.05 * SR)
    x = np.diff(np.random.randn(n + 1))
    return x * np.exp(-np.arange(n) / SR / 0.015) * 0.18


def _snare() -> np.ndarray:
    n = int(0.16 * SR)
    t = np.arange(n) / SR
    noise = np.random.randn(n) * np.exp(-t / 0.07)
    tone = np.sin(2 * np.pi * 190 * t) * np.exp(-t / 0.05)
    return (noise * 0.6 + tone * 0.4) * 0.4


def _pluck(freq: float, dur: float, wave_type: str, vel: float) -> np.ndarray:
    n = int(dur * SR)
    env = np.exp(-np.arange(n) / SR / (dur * 0.5))
    return _osc(freq, n, wave_type) * env * vel


def _pad(freq: float, dur: float, vel: float) -> np.ndarray:
    n = int(dur * SR)
    env = np.ones(n)
    a, r = int(0.05 * SR), int(0.20 * SR)
    if a:
        env[:a] = np.linspace(0, 1, a)
    if r and r < n:
        env[-r:] = np.linspace(1, 0, r)
    # two slightly detuned sines for warmth
    return (_osc(freq, n) + 0.6 * _osc(freq * 1.003, n)) * env * vel


def generate_bed(out_path: str | Path, *, duration: float = 24.0,
                 style: str = "upbeat", seed: int = 0) -> Path:
    np.random.seed(seed)
    sp = STYLES.get(style, STYLES["upbeat"])
    beat = 60.0 / sp["bpm"]
    bar = beat * 4
    total = int(duration * SR)
    buf = np.zeros(total)

    nbars = int(np.ceil(duration / bar)) + 1
    for b in range(nbars):
        ci = b % 4
        bs = int(b * bar * SR)
        # pad chord across the bar
        for m in CHORDS[ci]:
            _place(buf, bs, _pad(_midi_freq(m), bar, sp["pad"]))
        # bass on each beat
        for k in range(4):
            _place(buf, bs + int(k * beat * SR),
                   _pluck(_midi_freq(BASSES[ci]), beat * 0.9, "tri", sp["bass"]))
        # arpeggio in eighths
        if sp["arp"]:
            tones = CHORDS[ci]
            for e in range(8):
                m = tones[e % len(tones)] + 12
                _place(buf, bs + int(e * (beat / 2) * SR),
                       _pluck(_midi_freq(m), beat * 0.5, sp["arp_wave"], sp["arp_v"]))
        # drums
        for k in range(4):
            _place(buf, bs + int(k * beat * SR), _kick(sp["kick"]))
        if sp["hat"]:
            for e in range(8):
                _place(buf, bs + int(e * (beat / 2) * SR), _hat())
        if sp["snare"]:
            for k in (1, 3):  # beats 2 and 4
                _place(buf, bs + int(k * beat * SR), _snare())

    buf = buf[:total]
    # normalize + soft limit + fades
    peak = np.max(np.abs(buf)) or 1.0
    buf = np.tanh(buf / peak * 1.1) * 0.92
    fi, fo = int(0.05 * SR), int(0.4 * SR)
    buf[:fi] *= np.linspace(0, 1, fi)
    buf[-fo:] *= np.linspace(1, 0, fo)

    stereo = np.stack([buf, np.roll(buf, 60)], axis=1)  # tiny haas for width
    data = (np.clip(stereo, -1, 1) * 32767).astype("<i2")

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_path), "w") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())
    return out_path


def ensure_beds(music_dir: str | Path) -> dict[str, Path]:
    """Generate the standard bed set if missing; return {style: path}."""
    music_dir = Path(music_dir)
    beds = {}
    for i, style in enumerate(("upbeat", "driving", "chill")):
        p = music_dir / f"bed_{style}.wav"
        if not p.exists():
            generate_bed(p, duration=24.0, style=style, seed=i + 1)
        beds[style] = p
    return beds


if __name__ == "__main__":
    out = ensure_beds(Path(__file__).resolve().parents[3] / "assets" / "music")
    for k, v in out.items():
        print(k, v)
