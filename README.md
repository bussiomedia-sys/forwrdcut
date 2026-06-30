<div align="center">

# ForwrdCut

**An agent-driven AI video editor that cuts ads and social content like the best-performing posts on the platform.**

Local-first · non-destructive · reproducible · built to be driven by an AI agent end-to-end.

</div>

---

ForwrdCut is a video-editing **engine plus an editor's brain**. The engine does the media work
(FFmpeg under the hood); the brain — [`AGENTS.md`](AGENTS.md) and [`docs/`](docs/) — is a
distilled playbook that lets an AI agent (e.g. Claude Code) research, plan, cut, and ship
world-class short-form video without a human touching a timeline.

It was built in-house at [FORWRD](https://forwrd.co) to produce real, shipping ad creative, and
it's open-sourced so anyone can run an agent that edits at a high bar.

## Why it's different

- **It has taste, on purpose.** The repo ships an opinionated editing standard (hooks, retention
  mechanics, the ABCD ad framework, per-platform playbooks, brand-voice discipline) so the agent
  defaults to edits that *perform*, not just edits that render.
- **Audio-first, measured timing.** Voiceover (local neural TTS) is the spine; cut lengths are
  measured from the synthesized audio so callouts and captions land on the beat.
- **Designed graphics, not stock.** Big bold callouts, brand badges, star proof, CTA buttons,
  and generated end cards — composited to a brand system.
- **Every cut is an EDP.** Edits are plain-JSON **Edit Decision Plans**: reviewable, diffable,
  reproducible. The same EDP renders 16:9, 9:16, or 4:5.
- **Local + private.** FFmpeg + on-device Whisper + on-device Kokoro TTS. No footage leaves your
  machine; no API key required for the core loop.

## What it does

- Index & analyze footage: scene detection, word-level transcription, silence/loudness, hook &
  highlight scoring, auto jump-cuts (dead-air + filler removal), subject-tracked reframing.
- Plan: rule-based + agent-authored EDPs with a strategy planner.
- Render: multi-segment timeline, smart reframe (16:9 / 9:16 / 4:5), animated word-synced
  captions, designed overlays/callouts, color grade, ducked procedural music, loudness norm.
- Voiceover: pluggable TTS (Kokoro local · ElevenLabs · macOS `say`) with a brand lexicon.
- Drive it from Python, the `forwrdcut` CLI, or the **MCP server** for conversational control.

## Quickstart

```bash
# macOS / Apple Silicon. Requires FFmpeg (with VideoToolbox) + Python 3.12.
python3.12 -m venv .venv
.venv/bin/pip install -e .            # core
.venv/bin/pip install -e ".[voice]"   # + local voiceover (Kokoro)

# Download the Kokoro voice model into models/kokoro/ (see docs/ENGINE.md), then:
.venv/bin/forwrdcut scan               # index a footage library
.venv/bin/forwrdcut transcribe path/to/clip.mp4
```

Author an EDP and render it (see [`docs/ENGINE.md`](docs/ENGINE.md) for the full schema and the
measure-pass pattern, and [`examples/`](examples/) for real production scripts):

```python
from forwrdcut.config import load_config
from forwrdcut.render.timeline import render_timeline
edp = { "version": 1, "project": "demo", "target": {"width": 1920, "height": 1080, "fps": 30}, ... }
render_timeline(edp, "renders/demo.mp4", load_config())
```

## For agents

Point your coding agent at this repo and it reads [`AGENTS.md`](AGENTS.md) (and `CLAUDE.md`) as a
standing operating manual: the editing standard, the production loop (research → footage → script
+ VO → EDP → render → QC), the [platform playbooks](docs/PLATFORMS.md), and the
[engine reference](docs/ENGINE.md). There's a Claude Code skill at
[`.claude/skills/produce-ad`](.claude/skills/produce-ad/SKILL.md).

## Repo layout

```
AGENTS.md          the editor's brain (read this first)
CLAUDE.md          pointer for Claude Code
docs/              EDITING_PLAYBOOK · PLATFORMS · ENGINE · briefs/
src/forwrdcut/     the engine (analysis · strategy · render · audio · mcp · cli)
assets/            brand font (Inter, OFL), procedural music beds, sfx
examples/          real production scripts (reference patterns)
.claude/skills/    produce-ad skill
config.toml        brand, paths, render, captions, grade, music config
```

## Contributing

PRs welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). The north star: does this make the agent's
edits *better* (more scroll-stopping, higher view-through, more on-brand), or the engine more
capable/reliable? Keep edits non-destructive and every render reproducible.

## License

[MIT](LICENSE) © FORWRD. The bundled Inter font is licensed under the SIL Open Font License.
