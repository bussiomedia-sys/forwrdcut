# ForwrdCut — Platform Playbooks & Specs

Each placement is its own medium. Match the spec **and** the feel of that platform's best
content. The distilled version of every section is machine-readable in
`strategy/briefs.py` — `forwrdcut brief --platform meta_ad` (or the `platform_brief` MCP
tool) prints it. **Agents: read the brief before planning any ad or social edit.**

Numbers below come from platform-published research and current (2026) spec guides —
sources at the bottom. Update `briefs.py` and this file together.

## Meta (Facebook/Instagram) — Feed & Reels ads — `meta_ad`
- **Aspect:** 9:16 (1080×1920) primary; +4:5 (1080×1350) for feed. **Sound:** OFF by
  default — **85% of Facebook video is watched muted** → caption-first design; still
  `loudnorm` for the rest.
- **Hook economics (Meta research):** 47% of a video ad's value is delivered in the first
  3 seconds, 74% by 10 seconds. A healthy *hook rate* (3s views ÷ impressions) is **>30%**
  — design the first 2 seconds as a visual pattern-break with the product present.
- **Length:** Reels placement 6–15s; feed 15–30s.
- **Safe zones (Reels ads — stricter than organic):** top **14%**, bottom **35%**, sides
  **6%** are covered by UI (profile, caption, CTA button). Set
  `captions: {safe_bottom_frac: 0.35}` in the EDP for Reels-ad deliverables.
- **Structure:** hook → what it is → benefit + proof (stars/reviews/testimonial) →
  offer + CTA + risk reversal (guarantee/warranty). Product-true claims only — run
  `forwrdcut lint` with a brand kit.
- **Ad-set discipline:** ship 3+ *distinct concepts* (UGC, feature-showcase,
  problem/solution), not three hook-variants of one video.

## YouTube — skippable in-stream — `youtube_ad`
- **Aspect:** 16:9 (1920×1080). **Sound:** ON — the VO is the spine; callouts reinforce.
- **Constraints:** minimum 12s; **15–30s is the conversion sweet spot** (longer only if
  every second earns it). Skip button at **0:05** — treat 0:00–0:05 as a self-contained
  mini-ad.
- **Brand early:** ads that establish the brand before the skip button see **~40% higher
  view-through** (Google ABCD research — 17,000+ campaigns with Ipsos/Nielsen/Kantar).
  Brand bug on screen by 0:03.
- **ABCD:** **A**ttract (motion, faces, tight framing from frame one) · **B**rand (early +
  often) · **C**onnect (benefit through real use, not abstract claims) · **D**irect (CTA
  on screen *and* spoken; end card holds ≥2s with logo + offer + URL).
- **Two CTAs:** soft verbal mid-roll (for soon-skippers) + hard end card.
- **Production note:** lo-fi/authentic often *beats* polished for direct response — hook
  specificity and audio clarity matter more than gloss.

## YouTube — bumper — `youtube_bumper`
- **EXACTLY ≤6 seconds** (hard constraint), non-skippable, 16:9. One idea, brand visible
  throughout, end frame = logo + URL. Derive from the :30's single strongest beat.

## YouTube — Shorts (ads + organic) — `shorts_ad`
- 9:16 **native vertical — never letterbox a 16:9 ad into the Shorts feed**. Under 30s,
  ideally 15–20s. Shorts ads are non-skippable units between organic Shorts, so native
  feel wins. Bottom ~20% and right action rail are UI territory.

## Instagram Reels — organic — `reels_organic`
- 9:16, **15–30s is the completion-rate zone**; 35–90s only for genuinely strong
  storytelling. The **3-second rule** decides keep-watching vs scroll; cut every 0.5–1.5s
  in the first 5 seconds (pattern breaks beat intros).
- Original audio/voiceover gets algorithmic preference; watermarked cross-posts are
  penalized. 3–5 quality posts/week beats daily mediocrity. Safe zones: top 13% / bottom
  24% / sides 8% (the engine defaults).
- Platform roles: **TikTok = discovery; Reels = trust, retargeting, conversion.**

## TikTok — organic — `tiktok_organic`
- 9:16, 15–30s for trends/tips/humor (highest completion + shares). <1s hook — the first
  frame is also the thumbnail. Authentic > salesy: keep creator audio on UGC, jump-cut the
  dead air, soft brand sign-off. Music: bake a placeholder, then swap to a **trending
  in-app sound** at post time (licensing + algorithm boost). Bottom ~25% + right rail = UI.

## Landing-page hero loop — `landing_hero`
- Native aspect (16:9 desktop / 1:1 mobile), muted autoplay, seamless loop (first ≈ last
  frame). **No color grade** (true product color), no captions, no music — clean designed
  callouts timed to what's on screen.

## Aspect-ratio handling cheatsheet
- Target 16:9 from **vertical** sources: cover-crop centered macros; blur-pad full-product
  shots; reserve full-bleed for native-landscape clips. Shooting for ads? Capture
  landscape hero/macro coverage, not just vertical Reels footage.
- Target 9:16 from **landscape**: smart/subject-tracked reframe or center cover — never
  lose the subject; never ship black bars.

## Sources
- [Meta video ads: formats, specs & best practices 2026 (Benly)](https://benly.ai/learn/meta-ads/video-ads-guide)
- [First 3 seconds of a Facebook video ad (Coinis)](https://coinis.com/how-to/first-3-seconds-facebook-video-ad)
- [Meta Reels safe zones 2026 — 14/35/6 (Behaviour Digital)](https://behaviour.digital/post/meta-reels-safe-zone-14-top-35-bottom-6-sides-the-2026-official-guide)
- [Meta ads safe zones guide (Billo)](https://billo.app/blog/meta-ads-safe-zones/)
- [YouTube ads 2026 strategy guide (Digital Applied)](https://www.digitalapplied.com/blog/youtube-ads-2026-video-advertising-strategy-guide)
- [YouTube ad formats & specs 2026 (MB Advertising)](https://www.mbadv.agency/youtube-ads/youtube-ad-formats)
- [YouTube ad creative best practices (Stackmatix)](https://www.stackmatix.com/blog/youtube-ad-creative-practices)
- [TikTok best practices 2026 (Miraflow)](https://miraflow.ai/blog/tiktok-best-practices-2026-complete-guide-creators)
- [Instagram Reels for business 2026 (Hootsuite)](https://blog.hootsuite.com/instagram-reels/)
- [Reels vs TikTok 2026 (PostNitro)](https://postnitro.ai/blog/post/instagram-reels-vs-tiktok-2026-guide)
