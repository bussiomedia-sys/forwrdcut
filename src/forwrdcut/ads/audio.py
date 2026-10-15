"""Music for ads: the track carries the ad, the source sound is muted by default.

Always -14 LUFS integrated, -1.5 dBTP, 48 kHz AAC. The explicit `aresample=48000` matters: loudnorm
upsamples to 192 kHz internally and, left alone, the file comes out at 96 kHz, which some phones and
players won't play at all (the "there's no music on these" bug).
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def mux_music(video: Path, track: Path, out: Path, *, duration: float, offset: float = 0.0,
              fade: float = 0.5, lufs: float = -14.0, keep_source_db: float | None = None,
              drop_at: float | None = None, sfx: list[dict] | None = None, bitrate: str = "160k") -> Path:
    """Lay `track` (from `offset` seconds, looped if short) under `video`. With `keep_source_db`, the
    clip's own sound stays on top and the music sits that many dB under it. With `drop_at`, the track
    plays muffled and quiet until that second, then hits full: the "beat drop" reveal format. `sfx` is foley
    that matches something on screen (a ribbon pulled, tissue crinkling): [{file, at, gain_db}], mixed under
    the music before the final loudness pass so it stays in proportion."""
    music = (f"[1:a]atrim=0:{duration:.3f},asetpts=N/SR/TB,afade=t=out:st={max(0.0, duration - fade):.3f}"
             f":d={fade}")
    # the drop is applied after loudnorm: single-pass loudnorm is adaptive and would lift a quiet intro
    drop = (f",lowpass=f=700:enable='lt(t,{drop_at:.3f})',volume=0.3:enable='lt(t,{drop_at:.3f})'"
            if drop_at else "")
    sfx = sfx or []
    if sfx and keep_source_db is None:
        fc = f"{music},loudnorm=I=-20:TP=-3:LRA=11[m]"
        labels = "[m]"
        for k, s_ in enumerate(sfx, start=2):
            ms = int(float(s_["at"]) * 1000)
            fc += f";[{k}:a]aresample=48000,adelay={ms}|{ms},volume={s_.get('gain_db', -6)}dB[s{k}]"
            labels += f"[s{k}]"
        fc += (f";{labels}amix=inputs={len(sfx) + 1}:duration=first:normalize=0,"
               f"loudnorm=I={lufs}:TP=-1.5:LRA=11{drop},aresample=48000[a]")
    elif keep_source_db is None:
        fc = f"{music},loudnorm=I={lufs}:TP=-1.5:LRA=11{drop},aresample=48000[a]"
    else:
        fc = (f"{music},volume={keep_source_db}dB[m];[0:a]aresample=48000[s];"
              f"[s][m]amix=inputs=2:duration=first:normalize=0,loudnorm=I={lufs}:TP=-1.5:LRA=11,"
              "aresample=48000[a]")
    out.parent.mkdir(parents=True, exist_ok=True)
    extra = sum([["-i", str(s_["file"])] for s_ in sfx], [])
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-ss", f"{offset}", "-stream_loop", "-1",
                    "-i", str(track), *extra, "-filter_complex", fc, "-map", "0:v", "-map", "[a]", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", bitrate, "-ar", "48000", "-movflags", "+faststart",
                    "-t", f"{duration:.3f}", str(out)], check=True)
    return out
