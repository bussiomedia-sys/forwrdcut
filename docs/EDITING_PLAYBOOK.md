# ForwrdCut — Editing Playbook (the craft)

The depth behind [`../AGENTS.md`](../AGENTS.md). This is how you make an edit that performs,
not just an edit that's "done."

## Retention mechanics

**The hook (first 1s, and the first 5s on ads).**
- Lead with the most arresting frame you have, in motion, with a bold hook line. Front-load
  the payoff visual; never bury it behind a logo sting or a slow fade.
- Open a loop the viewer needs closed: a question, a curiosity gap, a contrarian claim, a
  pattern interrupt ("Most pickleball bags are an afterthought. These two aren't.").
- On skippable in-stream ads the **skip button appears at 0:05** — the first five seconds
  must work as a complete mini-ad: scroll-stopper + reason to stay + brand on screen.

**The body (open → close → next loop).**
- Pose tension, delay the answer, pay it off, then *immediately* raise the next question. A
  gap is always open. This is the single biggest lever on view-through.
- Each beat earns the next. If you can drop a beat and lose nothing, drop it.
- Vary shot scale and angle every cut. Repetition of framing reads as slow even at a fast cut rate.

**The pacing.**
- ~1.5–2.5s per beat for ads/short-form; tighter for comedy, slightly looser for lifestyle.
- Auto jump-cut talking segments to remove silence + "um/uh" (`analysis/jumpcut.py`).
- Motion on every shot (slow zoom in/out, punch). Static = dead, even for 1.5s.

**The ending.**
- Short-form: land a button/punchline or loop to frame one (replays inflate watch time).
- Ads: hard CTA + brand + offer + risk-reversal. End card holds ≥2s with logo + URL.

## Hooks that work (steal these shapes)
- **Problem/contrarian:** "Most X are an afterthought. This isn't."
- **Curiosity gap:** "Wait… is that a giant pickleball?" (answer withheld 1–2 beats)
- **Bold promise + specificity:** "Rebuilt from four thousand reviews."
- **You-already-do-this-wrong:** "You wouldn't put a $200 paddle in a $30 bag."
- **Demonstration:** open mid-action on the most satisfying product moment (a snap, a reveal).

## Ad archetypes (pick one per asset; don't blend three)
- **Feature breakdown / listicle:** fast premium showcase, one bold callout per feature.
  Algorithmically readable, packs variety. (The dual-bag YouTube ad uses this.)
- **Problem → solution story:** agitate a real pain, resolve with the product.
- **UGC / social proof montage:** real creator soundbites as the spine; authentic, sound-on.
- **Founder/explainer:** direct, credible, "why we built it."
- **Demonstration/oddly-satisfying:** let the product's best physical moment carry it.

When running paid: ship **distinct concepts** in an ad set (a feature-breakdown + a UGC + a
problem/solution), not three hook-variants of the same video.

## Footage selection (the part amateurs skip)
- Probe every source (orientation, duration). Build a **contact sheet** — one representative
  frame per clip, tiled, labeled with an index — and look at all of it before choosing.
- Map each beat to a **transcript-verified or eyes-verified** visual moment. When a reviewer
  says "fence hooks," they're showing fence hooks — that timestamp is your shot.
- For VO beats, anchor the VO line to the moment that *shows* what it describes (the VO
  replaces the source audio, so only the visual matters).
- Aspect fit: native-orientation first; cover-crop only centered macros; blur-pad full-bag
  shots; never crop a tall product down to a thin sliver.
- Reject dark/abstract/blurry frames for hero/hook beats — extract the candidate frame and
  confirm before committing.

## Sound design
- Sound-OFF platforms (Meta feed): captions carry everything; design for muted viewing.
- Sound-ON platforms (YouTube): VO/audio is the spine; text reinforces.
- Music bed **ducks** under VO/speech (sidechain). `loudnorm` to ~-14 LUFS so it sits right
  in-feed. **No whoosh / transition SFX** — hard cuts read more premium.
- VO storytelling (local Kokoro TTS) is great for ads; keep a brand pronunciation lexicon and
  spell numbers/symbols out in the VO line (captions transcribe the speech).

## Captions
- Animated word-synced styles (`box-pop` default: pop-in + active word highlighted) for
  short-form. Keep inside platform safe zones (off the UI: top bar, bottom caption/nav,
  right-side action buttons on 9:16).
- Brand the emphasis color; one highlight per line. Never let captions fight a big callout —
  suppress one of them.

## Color
- Apply a consistent brand grade (punch/warm/vibrant/clean or a LUT) so mixed sources feel
  like one piece — EXCEPT landing-page hero loops, which keep true product color (no grade).
