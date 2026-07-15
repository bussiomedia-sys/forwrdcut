# Changelog

## Unreleased

The "social-ad polish" pass — learnings from a real Meta pre-order campaign, generalized so
every edit benefits.

### Multi-use vertical + placement safety
- **`safe_upper` / `safe_lower` overlay positions** keep the wordmark, product, and headline
  inside the centre band that survives a **4:5 or 1:1 auto-crop** of a 9:16 master — so one
  9:16 render is safely multi-use across Meta feed/Reels/Stories.
- Overlay `position` now also documented end-to-end (`docs/ENGINE.md`).

### Overlays that look hand-made, not templated
- **`logo` overlay** — composite a real brand PNG (script wordmark, emblem) instead of a text
  pill; `width_frac`, soft `shadow`.
- **Overlay `fade`** — gentle alpha ease-in/out on any overlay instead of a hard pop.
- **Softer callouts** — a soft drop shadow (via a new `_with_shadow` helper) replaces the heavy
  black keyline; new `size_frac` / `max_width_frac` / `emphasis_style` (`color` word vs filled
  `chip`) / `upper` (sentence case) / `weight` options.

### Sound
- **Whimsical music-box bed** (`generate_whimsical_bed`: inharmonic bell + harp + pad, no drum
  kit) added to the default bed set — a gentle, wholesome score for lifestyle/product edits.

### Correctness (silent-failure fixes)
- **Mixed still + video timelines no longer drop beats.** JPEG stills decoded full-range and
  encoded `yuvj420p`; concat-copy against video's `yuv420p` silently held a frame in place.
  Segments now normalise to limited range, and the timeline verifies concat compatibility +
  output duration, falling back to a re-encode when they differ.
- **Claim lint:** lone number-words in ordinary English (e.g. *"the **one** that doesn't
  melt"*) are no longer misread as numeric claims; only numbers in numeric context convert.

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
