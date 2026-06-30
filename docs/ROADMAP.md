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
- [ ] **Beat-synced cutting.** Detect music beats/onsets; snap cuts and zoom-punches to the beat.
      This single thing is what makes an edit *feel* professionally cut. Highest wow.
- [ ] **One-call autonomous masterpiece.** Strengthen `auto` into a killer default on arbitrary raw
      input: transcribe → hook-detect → jump-cut → highlight-select → reframe → caption → beat-synced
      music → grade → render, with the taste rules enforced. The "drop in a raw clip, get a great
      Short" demo that sells the project.
- [ ] **Emphasis-aware dynamics.** Punch-in / speed-ramp / scale-pop on the emphasized word or the
      payoff beat (driven by transcript + loudness). The signature modern-edit feel.

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
