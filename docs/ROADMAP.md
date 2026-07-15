# ForwrdCut — Roadmap to the best AI video editor in the world

The [mission](../AGENTS.md) is a high bar: edits a stranger assumes a world-class human made,
produced autonomously. This is an honest map of where we are and what gets us there.

## What's already real (grounded in the engine, not aspirational)

- **Understanding:** library scan + probe · scene detection · word-level transcription (cached) ·
  silence/loudness analysis · hook-line detection + highlight scoring · auto jump-cut (dead-air +
  filler "um/uh" removal) · subject/face reframe tracking.
- **Craft:** multi-segment timeline · motion (zoom in/out/punch, auto-alternating) · reframe
  (cover / blur-pad / subject-tracked) · 4 animated word-synced caption styles · designed overlays
  (callout, CTA, badge, stars) · color grade (punch/warm/vibrant/clean + custom LUT) · procedural
  ducked music (upbeat/driving/chill) · transitions (hard cut + crossfade/dissolve) · loudnorm.
- **Voice:** pluggable TTS — Kokoro local (default, free) · ElevenLabs · macOS fallback · brand
  pronunciation lexicon.
- **Control:** CLI · 16 MCP tools for full conversational control · reproducible `.edp.json` per render.

## Our actual edge (where we win, and should press)

Manual tools (CapCut etc.) own a huge button surface + asset libraries. We do not compete there.
We win on **autonomy + taste + reproducibility + local/private**: the agent makes every editing
decision with an opinionated standard baked in, and any cut is a diffable plan. Pressing this edge
beats matching features.

## The path (prioritized by "wow per unit effort")

### Tier 1 — the moves that make output jaw-dropping
- [x] **Beat detection + beat-aligned cuts.** `analysis/beats.py` (exact grids from known-BPM beds +
      an onset/autocorrelation detector for arbitrary audio); `autoedit` nudges cut points onto the
      beat grid. Next: target beat-multiple segment durations so more cuts land on the beat.
- [x] **One-call autonomous edit.** `strategy/autoedit.py` + `forwrdcut short`: transcribe →
      hook-first jump-cut → reframe → word-synced captions → emphasis punches → beat-aligned cuts →
      ducked procedural music → loudnorm → render. Verified end-to-end (raw clip → finished Short).
- [x] **Emphasis-aware dynamics.** `analysis/emphasis.py` + render core: scale-pop punch on the
      emphasized word (transcript-driven), composed with the slow push. Next: optional speed-ramp.

### Tier 2 — reach & polish
- [ ] **Multilingual captions + translation** (Whisper translate) — autosubtitle in N languages.
- [ ] **Auto b-roll matching** — map transcript keywords to library/stock clips, overlay on talking-head.
- [ ] **Stock/asset integration** (Pexels/Pixabay) to fill b-roll gaps automatically.
- [ ] **More caption/text presets** — trend looks (bounce, gradient, glow, TikTok word-by-word).
- [ ] **Auto thumbnail/cover** — pick the best frame + title overlay for the post.
- [ ] **Format templates** — codified talking-head reel / listicle / before-after / UGC the agent instantiates.

### Tier 3 — trust & contribution
- [ ] **Runnable demo** — bundle a tiny CC0 sample clip + a `make demo` that renders a Short, with a GIF in the README.
- [ ] **Tests on a real render** + tighten CI from advisory lint to a green render smoke test.
- [ ] **Per-platform render presets** table · progress/telemetry · optional GPU encode paths.

## How to contribute against this

Pick an item, open an issue, and show a **before/after frame or clip** proving it lifts the output.
The bar for merge isn't "it works" — it's "the edit is visibly better." See
[`../CONTRIBUTING.md`](../CONTRIBUTING.md).
