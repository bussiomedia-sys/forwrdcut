# CLAUDE.md

This project is **ForwrdCut**, an agent-driven AI video editor.

**Read [`AGENTS.md`](AGENTS.md) first and follow it as your standing operating manual** — it
defines the editing standard (world-class short-form + ads), the production loop, the platform
playbooks, the brand-voice/claims discipline, and the quality bar. Depth lives in
[`docs/EDITING_PLAYBOOK.md`](docs/EDITING_PLAYBOOK.md), [`docs/PLATFORMS.md`](docs/PLATFORMS.md),
and [`docs/ENGINE.md`](docs/ENGINE.md).

Environment notes:
- Python 3.12 venv at `.venv` (the vision/TTS stack needs 3.12). FFmpeg with VideoToolbox.
- Drive the engine via an EDP → `render_timeline` (see `docs/ENGINE.md`), the `forwrdcut` CLI,
  or the MCP server. Sources are read-only; outputs go to `renders/`.
- No whoosh/transition SFX. Brand colors/fonts and spelling fixes live in config + the captions
  normalizer.
