# DECISIONS.md — stack choices & tradeoffs

Running log. Newest at top.

## 2026-06-23 — Voiceover storytelling (local Kokoro TTS)

- **Pluggable TTS (`audio/tts.py`):** `kokoro` (local neural, DEFAULT — `pip install kokoro-onnx`, models in `models/kokoro/`, ~310MB; worked first-try, no espeak needed), `elevenlabs` (only if `ELEVENLABS_API_KEY`), `say` (macOS fallback). All free except the optional ElevenLabs key. Voices liked: af_heart / am_michael / af_bella.
- **VO storytelling flow (`render_vo_segment` + timeline VO branch):** per-segment `voiceover` line → Kokoro synth → Whisper re-transcribe for word timing → captions word-synced to the VO → segment duration = VO length (video freezes via `tpad=stop_mode=clone` if footage shorter) → music **ducks** under VO (sidechaincompress). VO + word-timings cached in `cache/vo/` keyed by (voice, line) so 9:16/4:5 don't re-synthesize.
- **No whoosh on ads (user pref):** VO ads set `sfx: []` — clean hard cuts carried by narration. (SFX cue system still available for non-VO edits.)
- **Loudness:** added `edp["loudnorm"]` → `loudnorm=I=-14:TP=-1.5:LRA=11` finalize. VO ads went from ~-24 dB mean to ~-17 dB / -1 dB peak (proper social-ad loudness).
- Voices varied across the 5 ad angles for in-feed A/B; both formats; `make_meta_ads_vo.py`.

## 2026-06-23 — Procedural music + b-roll editing + Meta ad delivery

- **Procedural royalty-free music (`render/music_gen.py`):** numpy synth — pad chords (I-V-vi-IV) + bass + arp + kick/hat/snare, styles `upbeat`/`driving`/`chill`, 48k stereo WAV. **100% generated → zero licensing risk, safe for paid ads.** Beds cached in `assets/music/`. Mixed via existing `sfx.mix_music`; for speechless ads use `duck=false`, `gain≈0.8` (measured: mean ≈ -19 dB, headroom safe).
- **`mute_source` EDP flag:** b-roll carries ambient wind; render with silent source + SFX/music. Wired through `_render_core`/`render_segment`/`timeline`.
- **Multi-format:** render any EDP at multiple targets by overriding `edp["target"]`; ads delivered **9:16 (1080×1920)** + **4:5 (1080×1350)** for Reels/Stories + Feed. `reframe:"cover"` adapts crop; caption sizes are width-relative so they carry across.
- **Workflow scripts** (hand-authored EDPs, agent-as-brain): `make_blanket_videos.py` (5 single-source), `make_blanket_mashup.py` (hero+short combined), `make_meta_ads.py` (5 cold-traffic ad angles, music + both formats). Copy grounded in the live product page.

## 2026-06-22 — Polish pass: hook hardening + caption styles + music bed

- **Hook selector hardened (`scoring.find_hook_lines`):** now reconstructs **complete sentences** from word timestamps (not Whisper's mid-sentence fragments), skips <3-word fragments, penalizes run-ons/incomplete thoughts, and **rejects degenerate transcripts** (`<3` distinct words / no ≥4-char content word) so music-only clips don't yield garbage. Result: Ranger hook went from a run-on fragment → "It is the top selling bag in the industry." (2.2s); the music-only Unboxing (Whisper hallucinated "I I I") now correctly yields a captionless visual edit instead of a junk hook.
- **Caption style templates (`captions.CAPTION_STYLES`):** `bold-pop` / `karaoke` / `clean-minimal` (font scale, stroke, uppercase, highlight on/off, words-per-group). Threaded through pipeline → timeline; selectable via `--style` and EDP `captions.style`. Verified clean-minimal renders lowercase, no highlight.
- **Music bed (`sfx.mix_music`):** looped bed mixed under speech, **sidechain-ducked** (`sidechaincompress` present) with limiter; `--music` flag / EDP `music.file`. Timeline post-stages are now ordered concat → SFX → music → finalize.
- **`batch --source DIR`:** point the batch at any folder (not just media/source) — the entry point for editing an arbitrary content folder.

## 2026-06-22 — Batch "make me N TikToks" + iPhone stream fix

- **Batch (`strategy/batch.py`, `forwrdcut batch`, MCP `batch`):** ranks the library by a standalone clip-score (best hook + best highlight + has-speech + length), renders the top N trend-grounded clips. If fewer usable clips than N, pads with **variants** of the top clip (planner `variant=` picks a different hook + rotated highlight order). Verified: 3 distinct TikToks from the library (Ranger 23s, Unboxing 19.5s, IMG_0929 5s).
- **Bug found by batch & fixed:** iPhone `.MOV` carries a phantom second audio track with codec `unknown` plus `mebx` timed-metadata data streams. `-map 0:a?` grabbed the broken audio → `no decoder found for: none`. Fix: map only the first audio stream (`-map 0:a:0?`) and add `-dn -ignore_unknown`. Now robust to iPhone/gimbal containers.
- **Known quality gap (not a bug):** the rule-based hook scorer can pick a weak 1-word opening (Unboxing → "I"). Acceptable for v1; the LLM refiner / agent edit fixes it. Logged for the next pass.

## 2026-06-22 — SFX + subject-tracked reframe + live trend grounding

- **SFX (`render/sfx.py`):** local pack (whoosh/pop/riser/impact) **synthesized with FFmpeg lavfi** on first use — no downloads/licensing. Mixed at EDP cue points post-concat via `adelay`+`amix(normalize=0)`+`alimiter` with video stream copied (fast, lossless video). Speech stays dominant via per-cue gain (0.55).
- **Subject-tracked reframe (`analysis/reframe_track.py`, `render/reframe.py`):** OpenCV Haar face detection in a **subprocess** (cv2/av isolation again) → static subject-centered crop, or a comma-free linear **pan** if the subject drifts. **Robustness gate:** only trust tracking when a face appears in ≥`min_face_ratio` (0.35) of sampled frames — otherwise center-cover. This prevents Haar false positives on b-roll from cropping wrong (verified: Ranger product demo → correctly falls back to center; tracking engaged only when faces were consistent). Engages only when source is wider than 9:16.
- **Trend grounding (`strategy/trends.py`):** agent-driven. Fetched real 2026 short-form data via web search (TikTok sweet spot 21–34s; Product/Outcome-Showcase hooks ~2× views; 5–10 word hooks; bold stacked first-frame text; flat-retention/cut-dead-air). Saved as a **timestamped cache** (`cache/trends/<platform>_<niche>.json`); planner + MCP auto-load the freshest non-stale file. Engine itself makes no trend network calls — research is the agent's job (honors "fetch, don't fabricate").
- Finale verified: trend-grounded `plan` (length 24, trend goal) → hand-edited EDP (bold "THE #1 SELLING WEEKENDER BAG" hook, Product/Outcome-Showcase) → `render-plan` with SFX + reframe → 23s TikTok, ~7.6s render.

## 2026-06-22 — MCP server (Phase 4)

- Engine wrapped as a **FastMCP** stdio server (`mcp/server.py`, entry point `forwrdcut-mcp`). 13 tools: scan_library, list_clips, get_clip_info, analyze_clip, transcribe, generate_plan, get_plan, edit_plan, render_plan, render_preview, auto, render_slice, list_outputs. Registration: `claude mcp add forwrdcut -- <abs>/.venv/bin/forwrdcut-mcp`.
- **Trend research is intentionally NOT an engine tool.** Brain is agent-driven, so the controlling agent does web research and passes a `trends` dict into generate_plan/auto. Keeps the engine free of network calls (except optional Claude hook-polish) and honest about who searches.
- Verified: tools register (13) and `call_tool("list_clips")` returns the 5 indexed clips through the MCP path.

## 2026-06-22 — Strategy engine + multi-segment timeline (Phase 2 + 3)

- **Brain = agent-driven + pluggable** (user choice). The engine is deterministic; intelligence (strategy, hook copy, trend grounding) is supplied by the controlling Claude Code agent. A rule-based planner is the always-on baseline; `strategy/llm.py` adds Claude hook-polish **only if `ANTHROPIC_API_KEY` is set** (none currently) — never required.
- **Edit Decision Plan (EDP)** is plain JSON (`strategy/edp.py`): reviewable/editable, validated before render, and emitted as a sidecar for every output → reproducible.
- **Planner** (`strategy/planner.py`): front-loads the top hook line, appends top non-overlapping highlight windows, trims toward platform length (tiktok 27s / reels 30s / shorts 35s), payoffs ordered chronologically, SFX cue slots at cuts, music slot left for native in-app trending audio.
- **Timeline assembler** (`render/timeline.py`): renders each segment to a **normalized concat-safe intermediate** (same res/fps/codec + forced 48k stereo audio, silent `anullsrc` if source has none), then **stream-copy concat** (fast/lossless) with a **filter-`concat` re-encode fallback** on mismatch. Chosen over one giant filter_complex for robustness and because each segment reuses the proven slice renderer.
- **Render core refactor:** extracted `_render_core` shared by `render_slice` (single, writes sidecar) and `render_segment` (concat-safe, no sidecar). Output fps forced to 30 for clean caption alignment.
- Verified: `auto` on the 33s Ranger clip → 23s TikTok, hook + 3 payoffs, captions intact across all 4 concatenated segments, ~9s total.

## 2026-06-22 — Analysis layer: scenes + audio + highlight scoring (Phase 1)

- **Scene detection:** PySceneDetect `ContentDetector`, run in an **isolated subprocess**. Reason: OpenCV (PySceneDetect) and PyAV (faster-whisper) each bundle their own libav → loading both in one process triggers `objc[…] AVFFrameReceiver implemented in both …libavdevice…` (duplicate AVFoundation capture classes; benign for file decode but flagged as crash-risk). Subprocessing scenedetect keeps OpenCV out of the main interpreter → **0 warnings**, no shared-lib clash.
- **Audio:** ffmpeg `silencedetect` (dead-air/speech regions) + `ebur128` (integrated LUFS + true peak) parsed from stderr — no extra deps.
- **Scoring:** hook-line heuristic (brevity + curiosity/superlative cues + numbers/questions + opening bonus) and sliding-window highlights (speech density + scene-cut activity + non-silence). Verified it surfaces the real hook ("…top selling bag in the industry", score 4.6) and the best 6s window (0–6s).
- **`analyze --render`** runs the whole chain and auto-cuts the top highlight with word-synced captions. Full analysis of a 33s clip ≈ 20s (cached thereafter).

## 2026-06-22 — Word-synced animated captions (Phase 1 + 3)

- **Transcription:** `faster-whisper` (`small`, int8, CPU). 33s clip transcribed in ~27s incl. first-run model download; cached in SQLite by file hash thereafter (re-runs instant). Word-level timestamps captured.
- **Animated captions:** rendered as a **PNG-per-frame sequence** (Pillow) overlaid via a single `overlay` input — not per-word `enable=` overlays. Chosen because it generalizes to any animation (pop/fade/karaoke) with one overlay, and identical consecutive frame-states are **hard-linked** so a clip with few word changes costs few real renders even at 30fps.
- **Style:** rolling 3-word phrase groups, active word highlighted (`#FFE53B`), auto-wrapped, big bold + thick stroke, safe-zone placement. Hormozi/karaoke look.
- **Output fps forced to 30** (`render.fps`) so caption frame sequence and base video align 1:1 (sources here are 30 and 60fps).
- Verified: at t=1.0/2.2/5.0s the highlighted word advances with the voiceover ("WEEKENDER" → "THE" → "STRAP"). 9s render in 1.8s.

## 2026-06-22 — Phase 0 discovery + Phase 1/3 vertical slice

### Environment (verified)
- macOS 26.5.1, **Apple M5** (10 cores), 24 GB RAM, arm64.
- **FFmpeg 8.1** present with `h264/hevc/prores_videotoolbox` (HW encode), `libx264/x265/svtav1/vpx`, `libvmaf`, `audiotoolbox`.
- Homebrew 5.1.9.

### Decision: dedicated **Python 3.12** venv (not system 3.14)
- System Python is **3.14.4**. `opencv-python` ships **no wheel** for 3.14 (or 3.13) on macOS arm64 → would force a from-source build (slow/fragile). `numpy` 2.5 requires ≥3.12.
- `ctranslate2` (Whisper backend) *does* have 3.14 wheels, but OpenCV is the blocker.
- → `brew install python@3.12`; project runs in `.venv` (3.12.13). System Python untouched.

### Decision: **Pillow PNG overlays** for captions (not drawtext/ASS)
- This machine's FFmpeg is a **minimal build**: no `libfreetype`, `libass`, or `fontconfig`. So `drawtext`, `subtitles`, and `ass` filters are **unavailable**.
- Available and used instead: `overlay`, `crop`, `scale`, `scale_vt`, `zoompan`, `fade`, `xfade`, `loudnorm`, `afade`.
- → Captions are rasterized with Pillow to transparent RGBA PNGs and composited via the `overlay` filter. This is also the *more powerful* path (full font/stroke/emphasis control, word-by-word animation) and avoids modifying the user's ffmpeg.
- Alternative if richer text shaping is ever needed: `brew reinstall ffmpeg` with libass — deferred; not required.

### Decision: VideoToolbox HW encode by default
- `h264_videotoolbox` with `libx264` fallback (auto-detected via `pick_video_encoder`). 6s 1080×1920 slice encodes in ~2.9s.

### Decision: stdlib-first core (dataclasses + sqlite3 + tomllib)
- Media/probe models are plain dataclasses; index is SQLite; config is tomllib — so the engine core imports and runs with zero heavy deps. ML deps (Whisper/OpenCV/PySceneDetect) are lazy-imported only where used.

### Reframe approach
- Default `cover`: `scale=…:force_original_aspect_ratio=increase,crop` (zoom-to-fill center crop) — robust for any source orientation. `blur_pad` available only if `gblur` present (it is not in this build → falls back to cover). Subject-tracked auto-reframe is Phase 3.

### Niche
- Source footage + a connected Shopify store ⇒ brand + product context for trend research to ground against.
