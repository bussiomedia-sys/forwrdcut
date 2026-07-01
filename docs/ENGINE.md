# ForwrdCut — Engine Reference (how to drive it)

Local-first (FFmpeg does the media work), non-destructive (sources are never modified),
reproducible (every render writes an `.edp.json` sidecar). You drive it by authoring an
**EDP** and calling the renderer — from Python, the CLI, or the MCP server.

## The EDP (Edit Decision Plan)

Plain JSON, the single input to the timeline assembler. Author it, validate it, render it.

```jsonc
{
  "version": 1,
  "project": "yt_twobags_30_16x9",
  "platform": "youtube",
  "goal": "…what this cut is for…",
  "target": {"width": 1920, "height": 1080, "fps": 30},
  "captions": {"mode": "auto", "style": "box-pop", "position": "lower"},
  "voice": "am_michael",            // Kokoro voice for VO beats
  "mute_source": true,              // VO beats self-mute; set false to keep creator audio on SB beats
  "auto_motion": false,             // true = alternate slow push/pull on every shot
  "segments": [
    // VO beat — narration drives duration; source audio replaced; captions word-synced
    {"source": "clip.mp4", "in": 2.5, "out": 5.5, "role": "vo",
     "reframe": "cover", "voiceover": "Most pickleball bags are an afterthought.",
     "caption": "none"},            // "none" suppresses VO captions (let a callout carry the text)
    // Soundbite / b-roll beat — real audio (if mute_source=false), auto or static caption
    {"source": "review.mp4", "in": 68.3, "out": 72.3, "role": "seg",
     "reframe": "cover", "caption": "auto"}   // or {"text": "STATIC HOOK LINE"} or "none"
  ],
  "overlays": [
    {"type": "callout", "text": "840D *BALLISTIC* NYLON", "position": "lower", "start": 8.1, "end": 11.4},
    {"type": "badge",   "text": "FORWRD",  "position": "top-right", "start": 0.3, "end": 5.0},
    {"type": "stars",   "rating": 4.6, "text": "9,500+ PLAYERS", "position": "upper", "start": 26, "end": 29},
    {"type": "cta",     "text": "SHOP NOW · FORWRD.CO", "position": "lower", "start": 27, "end": 32}
  ],
  "music": {"file": "assets/music/bed_driving.wav", "gain": 0.16, "duck": true},
  "loudnorm": true,
  "transition": "cut",              // default hard cuts; "crossfade"/"dissolve" optional
  "sfx": []                         // keep empty — no whoosh
}
```

### Segments
- `voiceover` → Kokoro TTS synthesized (cached by `voice|text`), source audio replaced,
  duration = VO length (video freezes/clones last frame if shorter). Captions word-sync to the VO.
- `caption`: `"auto"` (word-synced from the clip's own speech), `"none"` (no captions —
  use when a big callout carries the text, or footage has burned-in captions), or
  `{"text": "…"}` (static styled headline).
- `reframe`: `"cover"` (center smart-crop), `"blur_pad"` (pillarbox with blurred surround),
  `"smart"` (subject/face-tracked reframe).
- `motion`: `"zoom_in" | "zoom_out" | "punch"` (or rely on `auto_motion`). Zooms use an
  **ease-in-out** curve (accelerate then settle — the pro look), not a linear creep.
- `speed`: playback multiplier — `0.5` = slow-mo, `2.0` = fast. The velocity-edit primitive
  (compose with beat detection: slow a beat, snap-cut, speed the next). Sped segments are
  silent (music carries) and their word captions are auto-rescaled. Default `1.0`.
- `shake`: `0..1` handheld camera jitter (sinusoidal x/y with auto crop headroom); composes
  with `motion`/`emphasis`. The punchy "energy" beat. Default `0.0`.
- `emphasis`: `true` to scale-pop on the segment's emphasized words (transcript-driven). Can
  also be set top-level to apply to all segments.

### Overlays (designed graphics, composited in a final pass)
- `callout` — big Inter-Black all-caps headline, white with one `*orange word*` (mark a
  **single** word with asterisks), heavy stroke, word-wrapped, `position` `center`/`lower`.
- `cta` — orange pill button. `badge` — small brand/credibility chip. `stars` — rating row
  + text. `progress` — thin retention bar. Each takes `start`/`end` (absolute seconds) and `position`.

### Music (`audio/music.py`) — licensed tracks first, procedural beds as fallback
Drop licensed audio into `assets/music/licensed/` (gitignored — never committed) or set
`[music] licensed_dir` in config.toml. The library detects BPM (`analysis/beats.py`),
duration, and a mood from filename tokens (`upbeat/driving/chill/cinematic`…), cached by
mtime. An EDP can then say `"music": {"mood": "upbeat", "duck": true}` — the timeline
resolves the best licensed track (procedural bed fallback). `forwrdcut music` lists the
library. Detected BPM feeds beat-aligned cutting.

### QC (`analysis/qc.py`) — the engine checks its own renders
`forwrdcut qc --file out.mp4` (or `qc_render()` / the MCP tool) reports machine-checkable
defects: video/audio stream mismatch (frozen-tail class), loudness off the -14 LUFS target,
true-peak clipping risk, mid-edit frozen video (end-card holds are allowed), black-frame
opens — plus a contact-sheet PNG. Writes `<render>.qc.json`; exits non-zero on issues so
scripts/CI can gate on it.

### Cinematic looks (top-level, opt-in finishing pass — `render/looks.py`)
- `cinematic: true` — convenience: 2.39:1 letterbox bars + a gentle vignette.
- `letterbox: 2.39` (custom bar ratio), `vignette: true|0..1`, `glow: 0..1` (highlight bloom),
  `grain: true|1..20` (film grain). Applied before the overlay pass, so text sits on top of bars.
  None set → pass skipped entirely.

### Templates (`strategy/templates.py`) — drop footage, ship
A template is a parameterized, beat-timed EDP. `beat_slideshow` (each clip = a beat-timed slot),
`feature_showcase` (hook + a bold callout per beat), and `photo_slideshow` (stills → Ken Burns
slots with longer dwell + optional titles). `render_template(cfg, name, clips, out,
aspect=…, music_style=…, cinematic=…)` probes clips, fills the slots, and renders. CLI: `forwrdcut
template --name beat_slideshow --clips … --aspect 9x16 [--cinematic]`.

## The measure-pass timing pattern (critical for VO + callouts)
Overlay `start`/`end` are **absolute** seconds, but VO-beat durations depend on the synthesized
audio. So: **pass 1** — synthesize each VO line (same cache key the timeline uses) and read each
wav's duration; accumulate offsets. **pass 2** — place each beat's callout at
`[offset+0.1, offset+dur-0.05]`, then render once. (See `make_youtube_ads.py` for the reference
implementation, incl. the generated end card and brand-badge-until-end-card logic.)

## Capabilities map (source files)
- **Analyze:** `analysis/scan.py` (library index), `scenes.py` (scene detect),
  `transcribe.py` (word-level Whisper), `audio.py` (silence/loudness), `scoring.py`
  (hook/highlight scoring), `jumpcut.py` (dead-air/filler removal), `reframe_track.py` (subject track),
  `beats.py` (beat grid/detection), `emphasis.py` (emphasis-word detection).
- **Plan:** `strategy/edp.py` (schema/validate/save), `planner.py`, `autoedit.py` (one-call
  autonomous edit), `templates.py` (beat-timed templates), `batch.py`, `trends.py`, `llm.py`.
- **Render:** `render/timeline.py` (assembler), `pipeline.py` (segment/VO render core; eased
  motion, speed, shake, emphasis pulses), `captions.py` + `caption_video.py` (animated captions),
  `graphics.py` (overlays/callouts), `looks.py` (cinematic letterbox/vignette/glow/grain),
  `reframe.py`, `grade.py`, `music_gen.py` (procedural beds), `sfx.py`, `annotate.py`.
- **Audio:** `audio/tts.py` (pluggable Kokoro / ElevenLabs / macOS `say`; lexicon for brand words).
- **Drive it:** `cli.py` (`forwrdcut scan|info|clips|transcribe|analyze|plan|auto|short|template|batch|slice`),
  `mcp/server.py` (MCP tools for conversational agent control).

## Config (`config.toml`)
Brand, paths, render target/encoder, caption style + safe zones + brand colors, color grade,
music/sfx gain + ducking, reframe (smart/track), transcription model, vision model. Per-EDP
`target`/`captions`/etc. override config defaults.

## Conventions
- Sources read-only; outputs to `renders/`; finals filed by the human into their library.
- Every render emits an `.edp.json` so any cut is reproducible and reviewable.
- Quick visual QC: extract frames from the finished mp4 and look before declaring done.
