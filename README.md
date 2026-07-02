<div align="center">

# ForwrdCut

**The AI video editor built to be driven by an agent — it researches, cuts, checks itself, and ships.**

[![ci](https://github.com/bussiomedia-sys/forwrdcut/actions/workflows/ci.yml/badge.svg)](https://github.com/bussiomedia-sys/forwrdcut/actions)
Local-first · non-destructive · reproducible · MIT

</div>

---

ForwrdCut is a video-editing **engine plus an editor's brain**. The engine does the media
work (FFmpeg under the hood). The brain — [`AGENTS.md`](AGENTS.md) + [`docs/`](docs/) — is a
distilled playbook of hooks, retention mechanics, per-platform best practices, and claims
discipline, so an AI agent (e.g. **Claude Code**) can research a product, find the shots,
write and voice a script, cut the edit, QC its own render, and ship — without a human
touching a timeline.

Built in-house at [FORWRD](https://forwrd.co) to produce real, shipping ad creative;
open-sourced so anyone can run an agent that edits at a high bar.

## Quickstart (3 commands)

```bash
pip install -e .            # in a Python 3.12 venv; FFmpeg required (brew/apt install ffmpeg)
forwrdcut init              # scaffold a project: config, folders, example brand kit
forwrdcut doctor            # verifies your setup and says exactly what to fix
```

Then drop clips (or photos) into `media/source/` and:

```bash
forwrdcut short --clip media/source/yourclip.mp4        # raw clip -> finished Short
forwrdcut template --name photo_slideshow --clips photos/*.jpg --aspect 9x16
forwrdcut find --q "the moment he opens the bag"        # shot search -> clip @ timestamp
forwrdcut qc --file renders/yourclip_short_9x16.mp4     # machine-checks the render
```

**Best with Claude Code:** open this repo (or your `forwrdcut init` project) in Claude Code and
just say what you want — *"make me a Meta ad for this product page"*. The agent reads
[`AGENTS.md`](AGENTS.md) and the [platform playbooks](docs/PLATFORMS.md) and runs the whole
production loop. An MCP server (`forwrdcut-mcp`) exposes 20+ tools for conversational control.

## What makes it different

- **It has taste, on purpose.** An opinionated editing standard ships with the repo — hooks in
  the first second, the 5-second skip wall, ABCD ad structure, one-idea-per-moment text rules,
  platform safe zones. The agent defaults to edits that *perform*, not just edits that render.
- **It checks its own work.** `forwrdcut qc` gates every render (loudness, clipping, stream
  mismatch, frozen frames, black opens + a contact sheet). Brand kits lint the *copy*: any
  stat or claim in a VO line must exist in your approved-claims registry — spoken numbers
  normalize, so "four point seven stars" matches "4.7 stars".
- **It iterates at conversation speed.** Segments are content-hashed and cached: editing one
  beat re-renders one beat (measured 6.6s fresh → 1.0s rerun → 1.3s one-beat change).
- **Every cut is an EDP** — a plain-JSON Edit Decision Plan: reviewable, diffable, and
  re-renderable to 16:9 / 9:16 / 4:5 / 1:1 from the same plan.
- **Local + private.** FFmpeg, on-device Whisper, on-device Kokoro TTS. No footage leaves
  your machine; no API key required for the core loop.

## Capabilities

| | |
|---|---|
| **Understand** | library scan · word-level transcription · scene detect · hook/highlight scoring · **shot search with timestamps** (`find`) · junk audit · beat detection |
| **Decide** | autonomous one-call edit (`short`) · beat-timed templates (video, features, photo slideshows) · rule + agent planning · brand kits |
| **Cut** | jump-cuts (dead air + fillers) · eased zoom · speed/velocity · camera shake · emphasis scale-pops on key words · beat-aligned cuts · smart reframe |
| **Dress** | word-synced animated captions (4 styles, safe-zoned) · designed callouts/CTA/badges/stars · cinematic looks (letterbox·vignette·glow·grain) · color grade/LUT · generated end cards |
| **Sound** | pluggable TTS (Kokoro local · ElevenLabs · `say`) · licensed-music library with BPM/mood auto-detect · procedural beds fallback · ducking · loudnorm + true-peak limiter |
| **Trust** | render QC gate · claims lint · reproducible `.edp.json` sidecars · incremental cache · 49-test suite run in CI with ffmpeg |

## The production loop the agent runs

1. **Research** the product page/reviews → approved claims + angles
2. **Find footage** (`find`, contact sheets) → map shots to beats
3. **Script + VO first** — audio is the spine; cut lengths are measured from it
4. **Author the EDP** → render (cached, parallel)
5. **QC** frames + audio (`qc`), lint the copy (`lint`), fix, re-render
6. Derive cutdowns/variants per platform

## Repo layout

```
AGENTS.md          the editor's brain (agents read this first)
docs/              EDITING_PLAYBOOK · PLATFORMS (per-format best practices) · ENGINE · research/
src/forwrdcut/     analysis · strategy · render · audio · media · mcp · cli
brands/            example brand kit (accent, banned words, approved-claims registry)
assets/            Inter font (OFL) · procedural music beds · put licensed music in music/licensed/
examples/          real production scripts (reference patterns)
```

## Contributing

PRs welcome — see [CONTRIBUTING.md](CONTRIBUTING.md) and [docs/ROADMAP.md](docs/ROADMAP.md).
The bar for merge isn't "it works" — it's "the edit is visibly better."

## License

[MIT](LICENSE) © FORWRD. Bundled Inter font under the SIL Open Font License.
