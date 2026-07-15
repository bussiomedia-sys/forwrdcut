---
name: produce-ad
description: >
  Produce a world-class video ad or social edit with the ForwrdCut engine. Use whenever the
  user wants to make an ad, a YouTube/Meta/TikTok/Reels video, ad creative, a product showcase,
  a hook test, or any short-form marketing video. Handles the full loop: research angles ->
  analyze footage -> script + VO -> author the EDP -> render -> QC -> cutdowns/variants.
---

# Produce an ad / social edit

Operate as the world-class editor defined in [`AGENTS.md`](../../../AGENTS.md). Follow that
standard and the production loop. This skill is the checklist for doing it end to end.

## 1. Brief & angles
- Confirm: product(s), placement/platform (sets aspect + sound + hook rules — see
  [`docs/PLATFORMS.md`](../../../docs/PLATFORMS.md)), length(s), and any offer/CTA.
- Research the live product page, reviews, and voice-of-customer. Pull **approved** stats and
  claims. Build angles from evidence, not guesses. Respect brand-voice rules (no em dashes, no
  "best/revolutionary", product-true claims, name real materials).

## 2. Footage
- Probe orientation/duration of candidate sources. Build a **contact sheet** (one frame per clip,
  tiled, indexed) and look at all of it. Map each beat to an eyes-verified visual moment.
- Aspect fit: native-orientation first; cover-crop centered macros; blur-pad full-bag shots.
- Need more footage? Search YouTube and download with yt-dlp into the project's footage folders.

## 3. Script + VO (audio is the spine)
- Write the script to the chosen archetype (feature-breakdown / problem-solution / UGC / etc.).
  One idea per beat. Spell out numbers/symbols in VO lines.
- Synthesize VO, then **measure each line's duration** — cut lengths come from the audio.

## 4. Author the EDP & render
- Lay beats (VO and/or soundbite), per-beat reframe, big **callouts** (one per beat, one orange
  word), brand badge in the hook, star proof, generated **end card** with logo + URL + offer.
- Use the **measure-pass** pattern to place overlays at correct absolute times (see
  [`docs/ENGINE.md`](../../../docs/ENGINE.md) and `examples/youtube_dual_bag_ad.py`).
- Ducked music bed, `loudnorm`, **no whoosh**. Render.

## 5. QC & deliver
- Extract frames across the finished render and look — crops, callout timing, legibility, brand
  spelling, hook strength, CTA. Fix the weakest beat, re-render.
- Derive the cutdowns/variants (e.g. :30 -> :15; distinct concepts for paid ad sets). File finals
  in the user's library. Confirm any uncertain product/labeling with the user.

Run the QC checklist in `AGENTS.md` §8 before calling it done.
