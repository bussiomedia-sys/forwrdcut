"""Platform briefs — per-format best practices as data, not tribal knowledge.

`forwrdcut brief --platform meta_ad` (or the MCP tool) prints the distilled playbook for
a format: spec, hook rule, structure, safe zones, a do/don't checklist, and the EDP
settings that implement it. Agents read the same data, so "make me a Meta ad" starts
from best practices every time — for any brand, driven by anyone.

Grounded in platform-published research and current (2026) specs — sources and the deep
version live in docs/PLATFORMS.md. Update both together.
"""
from __future__ import annotations

BRIEFS: dict[str, dict] = {
    "meta_ad": {
        "name": "Meta feed/Reels ad (cold traffic)",
        "spec": "9:16 1080x1920 primary (+4:5 1080x1350 for feed) · 30fps · 6-15s Reels, 15-30s feed",
        "sound": "OFF by default (85% watched muted) — captions carry the message; still mix "
                 "properly (loudnorm) for the 15% with sound",
        "hook": "<2s visual pattern-break. Meta's research: 47% of ad value lands in the first "
                "3s, 74% by 10s; a good hook rate (3s views/impressions) is >30%",
        "structure": ["hook (value promise / question / bold claim)", "what it is (product in use)",
                      "benefit + proof (stars/reviews/testimonial)", "offer + CTA + risk reversal"],
        "safe_zones": "Reels ads UI is aggressive: keep text/logo out of top 14%, bottom 35%, "
                      "sides 6% (set captions.safe_bottom_frac: 0.35 in the EDP)",
        "do": ["word-synced captions (caption-first design)", "product-true claims only (lint it)",
               "risk reversal (guarantee/warranty)", "end card with offer + URL",
               "3+ distinct concepts per ad set (not 3 hook-variants of one video)"],
        "dont": ["burying the product past 3s", "salesy voice with no proof", "store-wide stats "
                 "on a single-product ad", "text in the bottom 35%"],
        "edp": {"captions": {"mode": "auto", "style": "bold-pop", "position": "lower",
                             "safe_bottom_frac": 0.35},
                "emphasis": True, "loudnorm": True, "music": {"mood": "upbeat", "duck": True}},
    },
    "youtube_ad": {
        "name": "YouTube skippable in-stream ad",
        "spec": "16:9 1920x1080 · 30fps · ≥12s required; 15-30s sweet spot (up to 60s if every "
                "second earns it)",
        "sound": "ON — VO is the spine; big callouts reinforce, never duplicate verbatim",
        "hook": "Skip button at 0:05 — treat 0:00-0:05 as a self-contained mini-ad. Brand "
                "on-screen before the skip = ~40% higher view-through (Google/Ipsos ABCD research)",
        "structure": ["hook + brand bug by 0:03", "feature beats ~2-2.5s each (one callout per beat)",
                      "proof (stars/reviews/warranty)", "end card: logo + offer + URL, hold ≥2s",
                      "two CTAs: soft verbal mid-roll + hard end card"],
        "safe_zones": "keep text inside the center ~80% (player chrome + reframing)",
        "do": ["ABCD: Attract/Brand/Connect/Direct", "spoken numbers spelled out in VO",
               "eased motion on every shot", "lo-fi authentic can beat polished for DR"],
        "dont": ["slow fade-in opens", "logo sting before the hook", "claims not in the registry",
                 "letterboxed vertical footage"],
        "edp": {"platform": "youtube", "target": {"width": 1920, "height": 1080, "fps": 30},
                "emphasis": True, "loudnorm": True, "vignette": 0.25},
    },
    "youtube_bumper": {
        "name": "YouTube bumper ad",
        "spec": "16:9 · EXACTLY ≤6s (hard constraint) · non-skippable",
        "sound": "ON",
        "hook": "one idea only — a single visual beat + brand + 5-7 word message",
        "structure": ["hook/brand/message land together", "end frame = logo + URL"],
        "safe_zones": "center 80%",
        "do": ["cut the :30 down to its single strongest beat", "brand visible the whole 6s"],
        "dont": ["two ideas", "any setup that needs 3s to pay off"],
        "edp": {"target": {"width": 1920, "height": 1080, "fps": 30}, "loudnorm": True},
    },
    "shorts_ad": {
        "name": "YouTube Shorts ad / organic Short",
        "spec": "9:16 native vertical (never black-bar a 16:9) · <30s ideal 15-20s",
        "sound": "ON — but caption everything anyway",
        "hook": "<1s; open mid-action on the most arresting frame",
        "structure": ["hook", "fast beats (cut every 1.5-2.5s)", "payoff/CTA or loop to frame one"],
        "safe_zones": "bottom ~20% (title/subscribe UI), right side action rail",
        "do": ["native vertical framing", "word-synced captions", "beat-aligned cuts"],
        "dont": ["reformatted horizontal ads", "long intros"],
        "edp": {"platform": "shorts", "target": {"width": 1080, "height": 1920, "fps": 30},
                "emphasis": True, "loudnorm": True},
    },
    "reels_organic": {
        "name": "Instagram Reels (organic)",
        "spec": "9:16 1080x1920 · 15-30s = completion zone; 35-90s only for strong storytelling",
        "sound": "ON w/ original audio preferred by the algorithm — design sound-off safe anyway",
        "hook": "3-second rule; cut every 0.5-1.5s in the first 5s (pattern breaks beat intros)",
        "structure": ["hook", "open→payoff→re-hook loops", "land the ending or loop for replays"],
        "safe_zones": "top 13%, bottom 24%, sides 8% (engine defaults match)",
        "do": ["authentic > salesy", "voiceover/original audio", "trending-sound slot for the human",
               "3-5 posts/week beats daily mediocrity"],
        "dont": ["watermarked cross-posts", "hard-sell openings", "text under the UI"],
        "edp": {"platform": "reels", "emphasis": True, "loudnorm": True},
    },
    "tiktok_organic": {
        "name": "TikTok (organic)",
        "spec": "9:16 · 15-30s for trends/tips/humor (highest completion + shares)",
        "sound": "ON — native audio culture; TikTok = discovery, Reels = trust/conversion",
        "hook": "<1s, native feel; the first frame is the thumbnail",
        "structure": ["hook", "fast authentic beats", "payoff/punchline; soft brand sign-off"],
        "safe_zones": "bottom ~25% (caption/music UI), right action rail ~10%",
        "do": ["keep the creator's real audio when using UGC", "jump-cut dead air",
               "swap in a trending in-app sound before posting"],
        "dont": ["polished ad gloss", "baked-in licensed music you can't clear", "whoosh SFX"],
        "edp": {"platform": "tiktok", "loudnorm": True},
    },
    "landing_hero": {
        "name": "Landing-page hero loop",
        "spec": "native aspect (16:9 desktop / 1:1 mobile) · short seamless loop · muted autoplay",
        "sound": "none (dropped)",
        "hook": "n/a — it loops; first and last frames should match",
        "structure": ["clean product beats", "minimal designed callouts timed to what's on screen"],
        "safe_zones": "n/a",
        "do": ["true product color (no grade)", "no captions", "no music"],
        "dont": ["color grading (product accuracy matters)", "text overload"],
        "edp": {"grade": False, "loudnorm": False},
    },
}

ALIASES = {"meta": "meta_ad", "facebook": "meta_ad", "instagram_ad": "meta_ad",
           "youtube": "youtube_ad", "youtube_30": "youtube_ad", "bumper": "youtube_bumper",
           "shorts": "shorts_ad", "reels": "reels_organic", "tiktok": "tiktok_organic",
           "hero": "landing_hero"}


def get_brief(platform: str) -> dict:
    key = ALIASES.get(platform.lower().strip(), platform.lower().strip())
    if key not in BRIEFS:
        raise KeyError(f"unknown platform {platform!r}; have: {', '.join(sorted(BRIEFS))}")
    return {"key": key, **BRIEFS[key]}


def render_brief(platform: str) -> str:
    b = get_brief(platform)
    lines = [f"◆ {b['name']}  ({b['key']})",
             f"  spec  : {b['spec']}",
             f"  sound : {b['sound']}",
             f"  hook  : {b['hook']}",
             f"  safe  : {b['safe_zones']}",
             "  structure:"]
    lines += [f"    {i+1}. {s}" for i, s in enumerate(b["structure"])]
    lines.append("  do:")
    lines += [f"    ✓ {d}" for d in b["do"]]
    lines.append("  don't:")
    lines += [f"    ✗ {d}" for d in b["dont"]]
    lines.append(f"  EDP settings: {b['edp']}")
    lines.append("  (deep playbook + sources: docs/PLATFORMS.md)")
    return "\n".join(lines)
