from forwrdcut.strategy.brand import normalize_numbers, lint_edp

KIT = {
    "voice": {"no_em_dash": True,
              "banned_words": ["best", "revolutionary", "game-changer"]},
    "claims": {"approved": ["4.7 stars", "261 verified reviews", "lifetime warranty",
                            "600D x 900D ripstop TPU-coated nylon", "25 liters",
                            "buy one get the 2nd 50% off"]},
}


def _edp(vo=None, callout=None):
    edp = {"segments": [], "overlays": []}
    if vo:
        edp["segments"].append({"voiceover": vo})
    if callout:
        edp["overlays"].append({"type": "callout", "text": callout})
    return edp


def test_normalize_spoken_numbers():
    assert normalize_numbers("four point seven stars") == "4.7 stars"
    assert normalize_numbers("two hundred sixty one reviews") == "261 reviews"
    assert normalize_numbers("fifty percent off") == "50% off"
    assert normalize_numbers("no numbers here") == "no numbers here"


def test_approved_claims_pass():
    edp = _edp(vo="Four point seven stars. Two hundred sixty one reviews. "
                  "And a lifetime warranty.")
    assert lint_edp(edp, KIT) == []


def test_spoken_600d_matches_registry_600D():
    assert lint_edp(_edp(vo="Six hundred D ripstop. Built to last."), KIT) == []
    assert lint_edp(_edp(callout="600D *RIPSTOP*"), KIT) == []


def test_unapproved_number_is_flagged():
    issues = lint_edp(_edp(vo="Nine point nine stars from everyone."), KIT)
    assert any("9.9" in i for i in issues)


def test_unapproved_claim_language_is_flagged():
    issues = lint_edp(_edp(vo="Comes with a forever guarantee."), KIT)
    assert any("guarantee" in i for i in issues)


def test_banned_word_and_em_dash():
    issues = lint_edp(_edp(vo="The best pickleball bag.", callout="PREMIUM — DIALED"), KIT)
    assert any('banned word "best"' in i for i in issues)
    assert any("em dash" in i for i in issues)
