# CapCut capability landscape → ForwrdCut strategy

Synthesized from a broad YouTube sweep (~40 queries, ~280 videos) across CapCut's feature
surface. Goal: understand what CapCut *is* as an editor so ForwrdCut can match and beat it —
autonomously. Companion to [`capcut-techniques.md`](capcut-techniques.md) (shot-level technique).

## What CapCut actually offers (by volume of creator coverage)

1. **AI tools (largest category).** AI video generator (image→video, now wired to Sora 2 / Veo 3.1),
   AI design studio, auto-captions (+ styling/fixing), text-to-speech (many voices), background
   removal / auto-cutout / custom object removal, body tracking + face retouch, and **long-form →
   short-form** "magic" repurposing.
2. **Templates.** The viral mechanic: browse a trending, **beat-timed template**, drop your clips/
   photos into its slots, export a polished video in seconds (3D photo templates, slideshows, reels).
3. **Effects.** 2D→3D parallax, zoom+shake, glitch, text effects, "epic" stylized looks.
4. **Edit styles.** Cinematic, anime/AMV, meme, vlog, lyric video, photo→cinematic-motion.
5. **Transitions, color grading/LUTs, kinetic text/typography, velocity edits.**

## ForwrdCut posture (have / building / gap)

| CapCut area | ForwrdCut |
|---|---|
| Auto-captions (styled, word-synced) | ✅ 4 animated styles |
| Text-to-speech (voices) | ✅ Kokoro / ElevenLabs / say + lexicon |
| Beat sync | ✅ `analysis/beats.py` + autoedit beat-align |
| Velocity / speed ramps | ✅ per-segment `speed` |
| Eased zoom / motion | ✅ ease-in-out |
| Color grade / LUT | ✅ `render/grade.py` |
| Cinematic look (letterbox/vignette/glow/grain) | ✅ `render/looks.py` |
| Long-form → short-form | ✅ `forwrdcut short` (autoedit) |
| Subject tracking | ✅ reframe track (for crop) |
| **Templates (slot-fill, beat-timed)** | 🎯 **next — our EDP IS a template; build a registry** |
| Photo/stills → cinematic motion + beat slideshow | ⏳ high social value, easy (we have zoom+beats) |
| Camera shake / zoom-shake transition | ⏳ roadmap |
| 2D→3D parallax | ⏳ needs depth estimation |
| Background removal / auto-cutout / text-behind-subject | ⏳ needs a matting model (rembg/u2net) |
| AI image→video (Sora/Veo) | ⏳ optional pluggable generative backend |

## The strategic bet: a Template system

CapCut's templates are why non-editors make great videos fast. **A ForwrdCut template is a
parameterized EDP**: a named structure (hook → beats → CTA, or a beat-synced slideshow) with media
*slots*, a music bed, caption/overlay/look defaults, and beat timing — the agent (or a user) just
supplies clips and it auto-fills, beat-syncs, and renders. This is the highest-leverage direction
for "replace human editors": pick a proven format, drop footage, ship. Build `strategy/templates.py`
as a registry of template→EDP factories, exposed via CLI/MCP.

## Build order (wow × leverage)
1. **Template system** + 2–3 proven templates (beat slideshow, feature showcase, hook-listicle).
2. **Stills → cinematic motion** (Ken Burns + beat-synced photo slideshow).
3. **Camera shake / zoom-shake transitions.**
4. **Auto-cutout / text-behind-subject** (matting model) and **2D→3D parallax** (depth).
5. Optional **generative backend** (image→video) behind a clean interface.
