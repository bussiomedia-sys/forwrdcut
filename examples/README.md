# Examples

These are **real production scripts** used to ship FORWRD ad creative — included as reference
patterns, not turnkey samples. They point at a private footage library (absolute paths), so treat
them as worked examples of the workflow rather than scripts you can run unmodified.

- **`youtube_dual_bag_ad.py`** — the canonical reference. A 16:9 YouTube in-stream ad ("Two Bags,
  One Standard") built to the ABCD framework: VO spine + big designed callouts, the **measure-pass
  timing** pattern (synthesize VO → measure durations → place overlays at absolute times), a
  generated end card, brand badge in the hook, and a :15 bumper cutdown derived from the :30.
- **`meta_voiceover_ads.py`** — a batch of Meta VO ads (Kokoro narration over b-roll), showing the
  per-segment `voiceover` pattern and 9:16/4:5 reuse.

To adapt one: swap the source paths to your own footage, rewrite the beats/VO/callouts, and run it
with the `forwrdcut` package installed. See [`../docs/ENGINE.md`](../docs/ENGINE.md) for the EDP
schema and [`../AGENTS.md`](../AGENTS.md) for how to make the edit *good*.
