"""Brand kits + claims lint — brands as config, marketing claims as a checked registry.

A brand kit is a TOML file in ``<project>/brands/<name>.toml`` (see the committed
``brands/example.toml``): accent color, logo paths, banned words, and — the part that
prevents real mistakes — an **approved claims registry**. An EDP that says
``"brand": "forwrd"`` gets the kit's accent applied at render time and its copy linted.

The lint catches the failure modes we've actually hit:
  - a VO line claiming something the product doesn't do ("opens flat") — any sentence
    with numbers or claim language (stars/reviews/warranty/%/$/…) must be covered by
    an approved claim
  - banned hype words ("best", "revolutionary", …)
  - em dashes in on-screen copy (house style)

VO lines spell numbers out ("four point seven stars"), so the linter normalizes spoken
numbers to digits before matching against the registry.
"""
from __future__ import annotations

import re
import tomllib

from ..config import Config

_UNITS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
          "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
          "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
          "eighteen": 18, "nineteen": 19}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
         "seventy": 70, "eighty": 80, "ninety": 90}
_WORD = re.compile(r"[a-z0-9$%.']+")

CLAIM_KEYWORDS = {"stars", "star", "reviews", "review", "warranty", "guarantee",
                  "players", "%", "$", "percent", "dollars", "liters", "shipping",
                  "rated", "verified", "sold"}

_SCALES = {"thousand": 1000, "million": 1_000_000, "billion": 1_000_000_000}

# Words that, following a lone number word, mark it as an actual number rather than
# ordinary English ("five dollars" / "fifty percent" vs "one standard" / "two bags").
_NUMERIC_CONTEXT = {"point", "hundred", "off", "out"} | set(_SCALES)


def normalize_numbers(text: str) -> str:
    """Spoken numbers -> digits: 'four point seven stars' -> '4.7 stars',
    'two hundred sixty one' -> '261', 'fifty percent off' -> '50% off'.

    A *lone* number word only converts when it sits in numeric context (followed by
    'point'/'percent'/'dollars' or claim language). Otherwise English words that happen
    to be numbers stay words: "the one that doesn't melt" is a hook, not a claim about
    the quantity 1, and "two bags, one standard" must not read as the digits 2 and 1.
    Multi-word runs ("two hundred sixty one") are always numeric."""
    toks = text.lower().replace("-", " ").split()
    out: list[str] = []
    i = 0
    while i < len(toks):
        w = toks[i].strip(",.!?")
        if w in _UNITS or w in _TENS:
            # Accumulate in groups so scale words multiply only the current group:
            # "nine thousand five hundred" -> 9000 + 500, not (9*1000+5)*100.
            total, group, j = 0, 0, i
            for j in range(i, len(toks) + 1):
                t = toks[j].strip(",.!?") if j < len(toks) else ""
                if t in _UNITS:
                    group += _UNITS[t]
                elif t in _TENS:
                    group += _TENS[t]
                elif t == "hundred":
                    group = max(group, 1) * 100
                elif t in _SCALES:
                    total += max(group, 1) * _SCALES[t]
                    group = 0
                else:
                    break
            else:
                j = len(toks)
            val = total + group
            nxt = toks[j].strip(",.!?") if j < len(toks) else ""
            if j - i == 1 and nxt not in _NUMERIC_CONTEXT and nxt not in CLAIM_KEYWORDS:
                out.append(toks[i])
                i += 1
                continue
            # "four point seven" -> 4.7
            if j < len(toks) and toks[j].strip(",.!?") == "point":
                frac, j2 = [], j + 1
                while j2 < len(toks) and toks[j2].strip(",.!?") in _UNITS:
                    frac.append(str(_UNITS[toks[j2].strip(",.!?")]))
                    j2 += 1
                if frac:
                    out.append(f"{val}.{''.join(frac)}")
                    i = j2
                    continue
            out.append(str(val))
            i = j
        elif w == "percent":
            if out and re.fullmatch(r"[\d.]+", out[-1]):
                out[-1] += "%"
            else:
                out.append("%")
            i += 1
        elif w == "dollars":
            if out and re.fullmatch(r"[\d.]+", out[-1]):
                out[-1] = "$" + out[-1]
            else:
                out.append("$")
            i += 1
        else:
            out.append(toks[i])
            i += 1
    return " ".join(out)


def _tokens(text: str) -> set[str]:
    # '.' stays in the char class for "4.7"/"$179.99" but must be stripped from word
    # edges ("guarantee." != "guarantee")
    return {t.strip(".'") for t in _WORD.findall(normalize_numbers(text).lower())} - {""}


def _digits(tokens: set[str]) -> set[str]:
    """Numeric cores, so spoken '600 d' matches the registry's '600D' and '$179.99'
    matches '179.99': every token containing a digit contributes its number part."""
    out = set()
    for t in tokens:
        for m in re.findall(r"\d+(?:\.\d+)?", t):
            out.add(m)
    return out


def load_brand(cfg: Config, name: str) -> dict:
    """Load <project>/brands/<name>.toml. Raises FileNotFoundError with guidance."""
    path = cfg.root / "brands" / f"{name}.toml"
    if not path.exists():
        raise FileNotFoundError(
            f"brand kit not found: {path} (copy brands/example.toml and fill it in)")
    kit = tomllib.loads(path.read_text())
    kit.setdefault("brand", {})["slug"] = name
    return kit


def _texts_of(edp: dict) -> list[tuple[str, str]]:
    """(where, text) pairs worth linting: VO lines + on-screen overlay copy."""
    out = []
    for i, seg in enumerate(edp.get("segments", [])):
        if seg.get("voiceover"):
            out.append((f"segment[{i}].voiceover", seg["voiceover"]))
        cap = seg.get("caption")
        if isinstance(cap, dict) and cap.get("text"):
            out.append((f"segment[{i}].caption", cap["text"]))
    for i, ov in enumerate(edp.get("overlays", [])):
        if ov.get("text"):
            out.append((f"overlay[{i}].{ov.get('type', '?')}", ov["text"]))
    return out


def lint_edp(edp: dict, kit: dict) -> list[str]:
    """Check an EDP's copy against a brand kit. Returns human-readable issues."""
    issues: list[str] = []
    voice = kit.get("voice", {})
    banned = [b.lower() for b in voice.get("banned_words", [])]
    claims = kit.get("claims", {}).get("approved", [])
    claim_tokens = [_tokens(c) for c in claims]
    all_claim_digits = set().union(*(_digits(t) for t in claim_tokens)) if claim_tokens else set()

    for where, text in _texts_of(edp):
        low = " " + text.lower() + " "
        for b in banned:
            if re.search(rf"\b{re.escape(b)}\b", low):
                issues.append(f'{where}: banned word "{b}" in "{text}"')
        if voice.get("no_em_dash", True) and "overlay" in where and "—" in text:
            issues.append(f"{where}: em dash in on-screen copy")
        # claims discipline: number/claim-language must be covered by the registry
        toks = _tokens(text)
        digits = _digits(toks)
        claimy = bool(digits) or bool(toks & CLAIM_KEYWORDS)
        if claimy and claims:
            uncovered = digits - all_claim_digits
            keyword_hit = toks & CLAIM_KEYWORDS
            covered = any(len(toks & ct) >= 2 for ct in claim_tokens)
            if uncovered:
                issues.append(f"{where}: number(s) {sorted(uncovered)} not in the approved "
                              f'claims registry — "{text}"')
            elif keyword_hit and not covered and not digits:
                issues.append(f'{where}: claim language {sorted(keyword_hit)} matches no '
                              f'approved claim — "{text}"')
    return issues


def apply_brand(cfg: Config, kit: dict) -> None:
    """Apply kit style to the render config (accent color drives callouts/stars/captions)."""
    hl = kit.get("style", {}).get("highlight")
    if hl:
        cfg.data.setdefault("captions", {})["highlight"] = hl
