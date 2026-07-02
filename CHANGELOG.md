# Changelog

## 0.2.0 — 2026-07-01

The "compounding infrastructure" release: the engine now onboards strangers, finds shots,
iterates in ~1 second, checks its own output, and lints marketing claims.

### Onboarding
- `forwrdcut init` — scaffold a working project (config, folders, example brand kit, gitignore)
- `forwrdcut doctor` — environment checkup with exact fix hints (ffmpeg filters, encoders,
  models, music, brand kits)
- Shipped `config.toml` is now brand-neutral; friendly no-config error points to `init`

### Editing intelligence
- **Footage library brain** — `forwrdcut find --q "..."` ranks clips and answers with the
  matching transcript moment + timestamp; `forwrdcut audit` flags mislabeled junk
- **Beat detection** + beat-aligned cuts; **emphasis scale-pops** on key words
- **One-call autonomous edit** (`forwrdcut short`) and **templates**
  (`beat_slideshow` / `feature_showcase` / `photo_slideshow`); stills become Ken Burns shots
- **Eased zoom**, per-segment **speed** (velocity), **camera shake**, **cinematic looks**
  (letterbox / vignette / glow / grain)

### Sound
- **Licensed music library** (`assets/music/licensed/`, BPM/mood auto-detected,
  `music: {"mood": "upbeat"}` in any EDP); procedural beds as fallback
- Loudness chain hardened: one-pass loudnorm + true-peak limiter

### Trust
- **Render QC** (`forwrdcut qc`): stream mismatch, loudness, clipping, mid-edit freezes,
  black opens, contact sheet — machine-gates every deliverable
- **Brand kits + claims lint** (`forwrdcut lint`): approved-claims registry with
  spoken-number normalization; banned words; on-screen style rules
- **Incremental rendering**: content-hashed segment cache + parallel renders
  (measured 6.6s fresh → 1.0s rerun → 1.3s one-beat edit); temp dirs cleaned
- Single-pass finishing (look + overlays + loudnorm in one encode); CI runs the full
  test suite with ffmpeg

## 0.1.0 — 2026-06-29

Initial open-source release: EDP-driven timeline renderer, word-synced animated captions,
designed overlays, smart reframe, color grade, procedural music with ducking, Kokoro TTS
voiceover, transcription/scene/highlight analysis, jump-cuts, CLI + MCP server, and the
agent operating manual (AGENTS.md + docs).
