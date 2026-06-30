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
- `motion`: `"zoom_in" | "zoom_out" | "punch"` (or rely on `auto_motion`).

### Overlays (designed graphics, composited in a final pass)
- `callout` — big Inter-Black all-caps headline, white with one `*orange word*` (mark a
  **single** word with asterisks), heavy stroke, word-wrapped, `position` `center`/`lower`.
- `cta` — orange pill button. `badge` — small brand/credibility chip. `stars` — rating row
  + text. `progress` — thin retention bar. Each takes `start`/`end` (absolute seconds) and `position`.

## The measure-pass timing pattern (critical for VO + callouts)
Overlay `start`/`end` are **absolute** seconds, but VO-beat durations depend on the synthesized
audio. So: **pass 1** — synthesize each VO line (same cache key the timeline uses) and read each
wav's duration; accumulate offsets. **pass 2** — place each beat's callout at
`[offset+0.1, offset+dur-0.05]`, then render once. (See `make_youtube_ads.py` for the reference
implementation, incl. the generated end card and brand-badge-until-end-card logic.)

## Capabilities map (source files)
- **Analyze:** `analysis/scan.py` (library index), `scenes.py` (scene detect),
  `transcribe.py` (word-level Whisper), `audio.py` (silence/loudness), `scoring.py`
  (hook/highlight scoring), `jumpcut.py` (dead-air/filler removal), `reframe_track.py` (subject track).
- **Plan:** `strategy/edp.py` (schema/validate/save), `planner.py`, `batch.py`, `trends.py`, `llm.py`.
- **Render:** `render/timeline.py` (assembler), `pipeline.py` (segment/VO render core),
  `captions.py` + `caption_video.py` (animated captions), `graphics.py` (overlays/callouts),
  `reframe.py`, `grade.py`, `music_gen.py` (procedural beds), `sfx.py`, `annotate.py` (hero callouts).
- **Audio:** `audio/tts.py` (pluggable Kokoro / ElevenLabs / macOS `say`; lexicon for brand words).
- **Drive it:** `cli.py` (`forwrdcut scan|info|clips|transcribe|slice|auto`), `mcp/server.py`
  (MCP tools for conversational agent control).

## Config (`config.toml`)
Brand, paths, render target/encoder, caption style + safe zones + brand colors, color grade,
music/sfx gain + ducking, reframe (smart/track), transcription model, vision model. Per-EDP
`target`/`captions`/etc. override config defaults.

## Conventions
- Sources read-only; outputs to `renders/`; finals filed by the human into their library.
- Every render emits an `.edp.json` so any cut is reproducible and reviewable.
- Quick visual QC: extract frames from the finished mp4 and look before declaring done.
