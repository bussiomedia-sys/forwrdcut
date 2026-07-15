"""Local SFX pack generation + cue mixing.

No downloads / licensing concerns: the pack (whoosh, pop, riser, impact) is
synthesized with FFmpeg's lavfi sources on first use. `mix_into` lays SFX at the
EDP's cue points over the finished video's audio (video stream copied), with a
limiter to avoid clipping. Speech stays dominant via per-cue gain.
"""
from __future__ import annotations

from pathlib import Path

from ..config import Config
from ..media.ffmpeg import run, list_filters
from ..media.ffprobe import probe

# name -> lavfi generator args (before output path). Each ~0.1–0.8s.
SFX_DEFS: dict[str, list[str]] = {
    "whoosh": ["-f", "lavfi", "-i", "anoisesrc=color=brown:amplitude=0.5:duration=0.45",
               "-af", "highpass=f=200,lowpass=f=5000,afade=t=in:d=0.06,"
                      "afade=t=out:st=0.2:d=0.25,volume=2.0"],
    "pop": ["-f", "lavfi", "-i", "sine=frequency=880:duration=0.09",
            "-af", "afade=t=out:st=0.02:d=0.07,volume=1.5"],
    "riser": ["-f", "lavfi", "-i", "aevalsrc=sin(2*PI*(220*t+0.5*2225*t*t)):d=0.8:s=48000",
              "-af", "afade=t=in:d=0.1,afade=t=out:st=0.65:d=0.15"],
    "impact": ["-f", "lavfi", "-i", "sine=frequency=65:duration=0.35",
               "-af", "afade=t=out:st=0.05:d=0.3,volume=2.0"],
}


def ensure_pack(sfx_dir: str | Path) -> list[str]:
    """Generate any missing SFX wavs. Returns names created this call."""
    sfx_dir = Path(sfx_dir)
    sfx_dir.mkdir(parents=True, exist_ok=True)
    made = []
    for name, args in SFX_DEFS.items():
        out = sfx_dir / f"{name}.wav"
        if not out.exists():
            run([*args, "-ac", "2", "-ar", "48000", str(out)], desc=f"gen sfx {name}")
            made.append(name)
    return made


def mix_into(video: str | Path, cues: list[dict], out_path: str | Path, cfg: Config) -> Path:
    """Mix SFX cues (each {name, at}) into *video*'s audio → out_path (video copied)."""
    video, out_path = Path(video), Path(out_path)
    sfx_dir = cfg.path("sfx_dir")
    ensure_pack(sfx_dir)
    gain = float(cfg.data.get("sfx", {}).get("gain", 0.55))

    usable = [(c, sfx_dir / f"{c['name']}.wav") for c in cues
              if (sfx_dir / f"{c['name']}.wav").exists()]
    if not usable:
        # nothing to mix; just copy through
        run(["-i", str(video), "-c", "copy", "-movflags", "+faststart", str(out_path)],
            desc="sfx passthrough")
        return out_path

    inputs = ["-i", str(video)]
    for _, wav in usable:
        inputs += ["-i", str(wav)]

    parts, labels = [], []
    for idx, (cue, _) in enumerate(usable, start=1):
        ms = max(0, int(float(cue["at"]) * 1000))
        parts.append(f"[{idx}:a]adelay={ms}|{ms},volume={gain}[s{idx}]")
        labels.append(f"[s{idx}]")
    mix = (";".join(parts) + ";" + "[0:a]" + "".join(labels)
           + f"amix=inputs={len(usable) + 1}:normalize=0:dropout_transition=0[mx];"
           + "[mx]alimiter=limit=0.95[a]")

    run([*inputs, "-filter_complex", mix, "-map", "0:v", "-map", "[a]",
         "-c:v", "copy", "-c:a", "aac", "-b:a", str(cfg.render.get("audio_bitrate", "192k")),
         "-movflags", "+faststart", str(out_path)], desc="mix sfx")
    return out_path


def mix_music(video: str | Path, music_file: str | Path, out_path: str | Path,
              cfg: Config, *, gain: float | None = None, duck: bool = True) -> Path:
    """Mix a looped music bed under *video*'s audio (video copied). Ducks the music
    under speech via sidechaincompress when available, else mixes at low gain."""
    video, music_file, out_path = Path(video), Path(music_file), Path(out_path)
    gain = float(gain if gain is not None else cfg.data.get("music", {}).get("gain", 0.12))
    dur = probe(video).duration
    inputs = ["-i", str(video), "-stream_loop", "-1", "-i", str(music_file)]

    if duck and "sidechaincompress" in list_filters():
        fc = (f"[1:a]aresample=48000,atrim=0:{dur},volume={gain}[mraw];"
              f"[mraw][0:a]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=300[mduck];"
              f"[0:a][mduck]amix=inputs=2:normalize=0:dropout_transition=0[mx];"
              f"[mx]alimiter=limit=0.95[a]")
    else:
        fc = (f"[1:a]aresample=48000,atrim=0:{dur},volume={gain}[m];"
              f"[0:a][m]amix=inputs=2:normalize=0:dropout_transition=0[mx];"
              f"[mx]alimiter=limit=0.95[a]")

    run([*inputs, "-filter_complex", fc, "-map", "0:v", "-map", "[a]",
         "-c:v", "copy", "-c:a", "aac", "-b:a", str(cfg.render.get("audio_bitrate", "192k")),
         "-shortest", "-movflags", "+faststart", str(out_path)], desc="mix music bed")
    return out_path
