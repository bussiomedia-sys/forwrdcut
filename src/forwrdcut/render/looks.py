"""Cinematic finishing looks — a single optional filter pass applied to the assembled
video before the overlay/graphics pass.

These replicate the "instant cinematic" upgrades CapCut editors lean on:
  - letterbox  : 2.39:1 (or custom) black bars for a film feel
  - vignette   : darkened edges that focus the eye on center
  - glow/bloom : soft highlight bloom (screen-blend a blurred copy) — dreamy, premium
  - grain      : subtle film grain so footage doesn't look "digital-flat"

All are opt-in via EDP keys; with none set, ``build_look_graph`` returns None and the
timeline skips the pass entirely (no re-encode, no behavior change).

EDP keys (top level):
  "cinematic": true            # convenience: letterbox 2.39 + gentle vignette
  "letterbox": 2.39            # explicit aspect for the bars
  "vignette": true | 0.0..1.0  # darkened edges (strength via angle)
  "glow": 0.0..1.0             # bloom opacity (e.g. 0.30)
  "grain": true | 1..20        # film grain strength
"""
from __future__ import annotations


def build_look_graph(edp: dict) -> str | None:
    cinematic = bool(edp.get("cinematic"))
    letterbox = edp.get("letterbox", 2.39 if cinematic else None)
    vignette = edp.get("vignette", True if cinematic else None)
    glow = edp.get("glow")
    grain = edp.get("grain")
    if not any([letterbox, vignette, glow, grain]):
        return None

    simple: list[str] = []
    if letterbox:
        try:
            ratio = float(letterbox)
        except (TypeError, ValueError):
            ratio = 2.39
        barh = f"(ih-iw/{ratio:.4f})/2"        # bar height for a width-driven letterbox
        simple.append(f"drawbox=x=0:y=0:w=iw:h='{barh}':color=black:t=fill")
        simple.append(f"drawbox=x=0:y='ih-{barh}':w=iw:h='{barh}':color=black:t=fill")
    if vignette:
        # smaller angle = stronger darkening; map strength 0..1 -> angle PI/5..PI/2.5
        strength = 0.5 if vignette is True else max(0.0, min(1.0, float(vignette)))
        angle = 3.14159 / (5.0 - 2.0 * strength)
        simple.append(f"vignette=angle={angle:.4f}")
    if grain:
        amt = 8 if grain is True else max(1, int(grain))
        simple.append(f"noise=alls={amt}:allf=t")

    chain: list[str] = []
    cur = "0:v"
    if simple:
        chain.append(f"[{cur}]{','.join(simple)}[lk1]")
        cur = "lk1"
    if glow:
        op = max(0.0, min(1.0, float(glow if glow is not True else 0.30)))
        chain.append(f"[{cur}]split[g0][g1]")
        chain.append("[g1]gblur=sigma=18[gb]")
        chain.append(f"[g0][gb]blend=all_mode=screen:all_opacity={op:.3f}[lk2]")
        cur = "lk2"
    chain.append(f"[{cur}]format=yuv420p[vout]")
    return ";".join(chain)
