"""Tests for the CIP unchanged-claim-vs-body drift prefilter.

Spawned by escape esc-20260717-cip-unchanged-claim-drift (cowboy#275). The
co-occurrence prefilter (scan_text) is a hard, deterministic unit; the
corpus-level "no un-reviewed drift" assertion is xfail until the (B) modifier
detector is hardened to parameter level (see module docstring).
"""

from __future__ import annotations

import pytest

from marshal_core.checks.cip_unchanged_claim_drift import scan_corpus, scan_text

# The CIP-36 exemplar, reduced to the two co-occurring sentences that define the
# escape class. §8.3 is asserted unchanged AND redefined in the same document.
_CIP36_EXEMPLAR = """
## 4.3 Graduation
Eligibility and weighting are computed from published, reproducible testnet
metrics, redefining what §8.3 funds instead of the fixed drop schedule.

## 11. Relationship to existing specs
Mainnet supply, MIN_BASEFEE, and the §8.3 distribution schedule are unchanged.
"""

# A benign co-reference MUST NOT be flagged: §8.3 named unchanged, and merely
# *drawn from*, with no modifying verb bound to the section.
_BENIGN = """
The airdrop draws from the existing §8.3 Community/Airdrops bucket.
Mainnet supply and the §8.3 distribution schedule are unchanged.
"""


def test_prefilter_flags_cip36_exemplar():
    hits = scan_text("cip-36-phased-launch-cusd", _CIP36_EXEMPLAR)
    assert any(h.section == "§8.3" for h in hits), (
        "prefilter must surface the §8.3 unchanged-claim-vs-redefinition co-occurrence"
    )


def test_prefilter_ignores_benign_draws_from():
    hits = scan_text("cip-benign", _BENIGN)
    assert hits == [], f"benign 'draws from' co-reference must not be flagged: {hits}"


@pytest.mark.xfail(
    reason="skeleton: the (B) modifier detector is section-number-level, not "
    "parameter-level, so it cannot yet decide which live-corpus co-occurrences "
    "are genuine drift vs benign. Permanent guard is the review-lens hazard; "
    "harden this to parameter matching before flipping to a hard corpus gate.",
    strict=False,
)
def test_corpus_has_no_unreviewed_unchanged_drift():
    hits = scan_corpus()
    assert hits == [], (
        "CIP asserts a section unchanged while its body modifies it:\n"
        + "\n".join(f"  {h.cip} {h.section}: {h.unchanged_line!r} vs {h.modify_line!r}" for h in hits)
    )
