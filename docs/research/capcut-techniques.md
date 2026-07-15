# CapCut technique teardown → ForwrdCut

Distilled from popular CapCut editing tutorials (15 Tricks, 17 Effects, velocity/beat-sync/
quality guides). The goal: replicate the techniques that make edits *feel* professionally cut,
as agent-driven engine capabilities (FFmpeg-based, EDP-controlled).

## Technique catalog → status

| Technique | What it does | ForwrdCut status |
|---|---|---|
| **Eased zoom** (bezier ease on keyframed zoom) | the #1 "pro vs amateur" tip — zoom accelerates then settles | ⚠️ had linear zoom → **now eased** |
| **Velocity / speed ramp** (0.25× → cut on beat → 2×) | slow-mo + snap-fast, the signature short-form punch | ⚠️ **now: per-segment `speed`** |
| **Beat-synced cutting** (auto beat markers) | cuts land on the music beat | ✅ `analysis/beats.py` + autoedit beat-align |
| **Fake camera move** (position keyframes) | pan/drift across a static shot (Ken Burns) | ⏳ planned (have zoom; add pan x/y) |
| **Cinematic letterbox bars** | 2.39:1 black bars for film feel | ⏳ planned (cheap) |
| **Vignette** | darkened edge, focus center | ⏳ planned (FFmpeg `vignette`) |
| **Bloom / edge-glow / light leak** | dreamy highlight bloom, overlay leaks | ⏳ planned (gblur+screen blend) |
| **Selective color** (isolate one hue) | desaturate all but one color | ⏳ planned (HSL) |
| **Spotlight mask** (darken + inverse mask) | highlight a region of frame | ⏳ planned |
| **Progress bar** | thin bar reveals across the clip | ⏳ planned (overlay type) |
| **Video-in-text / text-in-video** | footage masked into letterforms | ⏳ niche |
| **3D parallax zoom** (subject/bg independent) | depth on a flat shot | ⏳ niche (needs depth/seg) |
| **Color grade** (contrast/sat/sharpen/highlights) | unify + punch | ✅ `render/grade.py` |
| **Text behind subject / motion-tracked text** | text composited behind / following subject | ⏳ (have subject track for reframe) |
| **Captions, TTS, thumbnails, upscale** | — | ✅ captions+TTS; upscale/thumbnail ⏳ |

## Why these two first
- **Eased zoom** affects *every* shot in *every* edit — replacing linear drift with an
  ease-in-out curve is the single highest-leverage polish, and it's exactly the tip every
  CapCut pro stresses ("change the curve to ease, now it looks like After Effects").
- **Per-segment speed** is the velocity-edit primitive. The tutorials build "velocity edits" by
  splitting on beats and setting constant speeds per piece (0.25× then 2×) — so a per-segment
  `speed` multiplier, composed with our beat detection, *is* the velocity edit.

## Next (ranked by wow/effort)
1. Cinematic letterbox + vignette (cheap, premium) — finishing options.
2. Camera shake on beats/impacts (crop jitter) + Ken Burns pan.
3. Bloom/edge-glow + light-leak overlays.
4. Selective color, spotlight mask, progress-bar overlay.
