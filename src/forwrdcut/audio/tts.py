"""Pluggable text-to-speech (voiceover) for the editor.

Providers (auto-selected, override with `provider`):
  - kokoro      local neural (kokoro-onnx). Free, on-device, natural. DEFAULT.
  - elevenlabs  best quality; used only if ELEVENLABS_API_KEY is set.
  - say         macOS built-in; zero-install fallback (lower quality).

`synthesize()` returns a 48 kHz mono WAV ready to mix. Heavy imports are lazy.
"""
from __future__ import annotations

import os
import re
import subprocess
import urllib.request
from functools import lru_cache
from pathlib import Path

from ..config import Config, load_config
from ..media.ffmpeg import run as ffrun

# Pronunciation lexicon: respell out-of-dictionary / brand words so the TTS G2P
# says them correctly (e.g. "pickleball" -> "pickly-ball" without this). Captions
# are unaffected — they come from Whisper transcribing the spoken audio.
_LEXICON = {
    r"\bpickleball\b": "pickle ball",
    r"\bpickleballs\b": "pickle balls",
    r"\bforwrd\b": "forward",
}


def apply_lexicon(text: str) -> str:
    for pat, repl in _LEXICON.items():
        text = re.sub(pat, repl, text, flags=re.IGNORECASE)
    return text

# Good defaults. Kokoro v1.0 voices: af_heart/af_bella/af_nicole (F),
# am_michael/am_adam (M), bf_emma (F-GB), bm_george (M-GB), ...
KOKORO_DEFAULT_VOICE = "af_heart"
ELEVEN_DEFAULT_VOICE = "21m00Tcm4TlvDq8ikWAM"  # "Rachel"


def _kokoro_paths(cfg: Config):
    base = cfg.root / "models" / "kokoro"
    return base / "kokoro-v1.0.onnx", base / "voices-v1.0.bin"


def kokoro_available(cfg: Config) -> bool:
    onnx, voices = _kokoro_paths(cfg)
    if not (onnx.exists() and voices.exists()):
        return False
    try:
        import kokoro_onnx  # noqa: F401
        return True
    except Exception:
        return False


@lru_cache(maxsize=1)
def _kokoro(onnx_str: str, voices_str: str):
    from kokoro_onnx import Kokoro
    return Kokoro(onnx_str, voices_str)


def _to_wav48(src: Path, out_wav: Path) -> Path:
    ffrun(["-i", str(src), "-ar", "48000", "-ac", "1", str(out_wav)], desc="tts->wav48")
    return out_wav


def _synth_kokoro(text, out_wav, cfg, voice, speed) -> Path:
    import soundfile as sf
    onnx, voices = _kokoro_paths(cfg)
    k = _kokoro(str(onnx), str(voices))
    samples, sr = k.create(text, voice=voice or KOKORO_DEFAULT_VOICE,
                           speed=speed, lang="en-us")
    raw = out_wav.with_suffix(".raw.wav")
    sf.write(str(raw), samples, sr)
    _to_wav48(raw, out_wav)
    raw.unlink(missing_ok=True)
    return out_wav


def _synth_say(text, out_wav, voice) -> Path:
    aiff = out_wav.with_suffix(".aiff")
    cmd = ["say", "-o", str(aiff)]
    if voice:
        cmd += ["-v", voice]
    cmd += [text]
    subprocess.run(cmd, check=True)
    _to_wav48(aiff, out_wav)
    aiff.unlink(missing_ok=True)
    return out_wav


def _synth_elevenlabs(text, out_wav, voice) -> Path:
    key = os.environ["ELEVENLABS_API_KEY"]
    voice_id = voice or ELEVEN_DEFAULT_VOICE
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        data=__import__("json").dumps({
            "text": text, "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }).encode(),
        headers={"xi-api-key": key, "Content-Type": "application/json",
                 "Accept": "audio/mpeg"},
        method="POST",
    )
    mp3 = out_wav.with_suffix(".mp3")
    with urllib.request.urlopen(req) as resp, open(mp3, "wb") as f:
        f.write(resp.read())
    _to_wav48(mp3, out_wav)
    mp3.unlink(missing_ok=True)
    return out_wav


def resolve_provider(cfg: Config, provider: str = "auto") -> str:
    if provider != "auto":
        return provider
    if os.environ.get("ELEVENLABS_API_KEY"):
        return "elevenlabs"
    if kokoro_available(cfg):
        return "kokoro"
    return "say"


def synthesize(text: str, out_wav: str | Path, *, cfg: Config | None = None,
               provider: str = "auto", voice: str | None = None,
               speed: float = 1.0) -> Path:
    cfg = cfg or load_config()
    out_wav = Path(out_wav)
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    text = apply_lexicon(text)
    prov = resolve_provider(cfg, provider)
    if prov == "kokoro":
        return _synth_kokoro(text, out_wav, cfg, voice, speed)
    if prov == "elevenlabs":
        return _synth_elevenlabs(text, out_wav, voice)
    return _synth_say(text, out_wav, voice)
