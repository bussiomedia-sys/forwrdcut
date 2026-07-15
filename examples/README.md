# Examples

- **`quickstart_ad.py`** — a self-contained, runnable demo. It generates its own placeholder
  footage with ffmpeg and builds a 3-beat vertical ad (hook → benefit → CTA) with timed callouts
  and a ducked music bed, so it runs anywhere with no external assets:

  ```bash
  python examples/quickstart_ad.py
  ```

  It's the canonical reference for the workflow: **author an EDP, then render it.** To make a real
  ad, swap the generated clips for your own footage and rewrite the beats, callouts, and VO.

See [`../docs/ENGINE.md`](../docs/ENGINE.md) for the full EDP schema and
[`../AGENTS.md`](../AGENTS.md) for how to make the edit *good*.
