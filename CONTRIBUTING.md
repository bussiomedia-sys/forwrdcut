# Contributing to ForwrdCut

Thanks for helping build the best open AI video editor. Two kinds of contributions matter most:

1. **Better taste** — improvements to the editing brain ([`AGENTS.md`](AGENTS.md), [`docs/`](docs/))
   that make the agent's edits more scroll-stopping, higher view-through, or more on-brand.
2. **Better engine** — new capabilities or more reliable rendering in `src/forwrdcut/`.

## Ground rules (the things that make this engine good)

- **Non-destructive.** Never modify source footage. Outputs go to `renders/`.
- **Reproducible.** Every render should emit an `.edp.json`. Prefer EDP-driven features over
  one-off scripts.
- **No whoosh.** No transition SFX. Hard cuts by default.
- **Product-true.** Never hard-code fabricated stats/claims into examples or defaults.
- **Local-first.** Keep the core loop runnable with FFmpeg + on-device models, no API key.

## Dev setup

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e ".[voice,dev]"
.venv/bin/ruff check src
.venv/bin/pytest          # if/when tests are present
```

## Workflow

1. Open an issue describing the change (bug, capability, or a taste/playbook improvement).
2. Branch, implement, and include a tiny repro or a before/after frame where it helps.
3. Keep PRs focused. Match the surrounding code's style and density.
4. Maintainers review; approved changes merge. For ad/playbook changes, explain *why it lifts
   performance*, not just what changed.

By contributing you agree your work is licensed under the repository's [MIT License](LICENSE).
