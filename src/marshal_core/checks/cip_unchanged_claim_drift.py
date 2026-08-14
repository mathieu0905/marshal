"""CIP "unchanged / not-amended" claim-vs-body drift check.

Permanent guard spawned by escape `esc-20260717-cip-unchanged-claim-drift`
(cowboyinc/cowboy#275 — CIP-36 §11 asserts "the §8.3 distribution schedule …
[is] unchanged" while §4.3 redefines that bucket's emission model from the WP
§8.3 row's normative "2 drops (TGE + 6 months)" to a metric-based testnet-
performance airdrop, with no declared whitepaper amendment). The amount/supply
(2% / 20M) is genuinely untouched — the *emission model / eligibility basis* is
the cell that changed. Class: **a CIP claims a WP/CIP section is unchanged or
not-amended while its own normative body modifies a parameter that section
governs.**

The check parses each CIP for two things and flags their co-occurrence for human
review:

  (A) an "unchanged" assertion naming a whitepaper (or CIP) section — e.g.
      "the §8.3 distribution schedule … are unchanged", "does not amend the
      whitepaper", "CIP-12 … Unchanged".
  (B) a normative modification (MUST/redefine/replace/set/new) elsewhere in the
      same CIP that references the same section number.

When (A) and (B) name the same section, the "unchanged" claim is *suspect* and
MUST be human-confirmed: either the change is legitimate governance evolution
that should be declared as an amendment, or the "unchanged" wording is wrong.

NOTE (skeleton / xfail — pending mechanization): distinguishing a genuine
contradiction (§4.3's metric airdrop overwriting §8.3's emission-model cell)
from a benign co-reference ("§8.3 is unchanged; we merely draw from its existing
bucket") is a semantic judgment. That judgment is why the escape's permanent
guard is a **review-lens hazard** (`hazard:cip-unchanged-claim-drift`, fed to the
spec-governance review via the `ratchet:spec-conformance` lens), not a hard gate.
This module is the mechanization *seam*: a cheap co-occurrence prefilter that
narrows the reviewer's attention to the CIP+section pairs worth reading. Harden
the (B) detector (parameter-level, not just section-number, matching) before
flipping `xfail` to a hard assertion — until then it stays advisory, mirroring
the `system_actor_addrmap` parser's staged hardening.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

WORKSPACE = Path("/home/ubuntu/workspace")
COWBOY_CIPS = WORKSPACE / "cowboy" / "docs" / "cips"

# "§8.3", "section 8.3", "WP §8.3", "CIP-12". Captures the bare section token.
_SECTION = r"(?:§\s*\d+(?:\.\d+)*|CIP-\d+)"

# (A) An "unchanged / not amended" assertion. Matched within a single line or a
# short window so an unrelated later "unchanged" elsewhere doesn't bind.
_UNCHANGED = re.compile(
    r"(?P<sec>" + _SECTION + r")[^.\n]{0,80}?\b(?:unchanged|not amended|untouched)\b"
    r"|(?:\bunchanged\b|\bnot amended\b|\buntouched\b)[^.\n]{0,80}?(?P<sec2>" + _SECTION + r")"
    r"|does\s+not\s+amend\s+the\s+whitepaper",
    re.IGNORECASE,
)

# (B) A normative modification tied to a section. Deliberately broad on the verb
# so the prefilter over-includes (reviewer prunes); narrow on requiring a section
# token nearby so it does not fire on every MUST in the document.
_MODIFY = re.compile(
    r"(?P<sec>" + _SECTION + r")[^.\n]{0,120}?"
    r"\b(?:redefin\w+|replac\w+|overwrit\w+|MUST\b|new basis|instead of|"
    r"rework\w*|change\w*|amend\w*)\b"
    r"|\b(?:redefin\w+|replac\w+|overwrit\w+|new basis|instead of)\b"
    r"[^.\n]{0,120}?(?P<sec2>" + _SECTION + r")",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class DriftHit:
    cip: str            # file stem, e.g. "cip-36-phased-launch-cusd"
    section: str        # the shared section token, e.g. "§8.3"
    unchanged_line: str
    modify_line: str


def _norm_section(tok: str) -> str:
    """Normalize a section token for equality: strip spaces, lowercase CIP."""
    return re.sub(r"\s+", "", tok).lower()


def _sections(match: re.Match) -> set[str]:
    # Named groups declared anywhere in the pattern are always addressable and
    # return None for the alternative that didn't match — no guard needed.
    out = {_norm_section(v) for v in (match.group("sec"), match.group("sec2")) if v}
    if not out and "amend the whitepaper" in match.group(0).lower():
        out.add("whitepaper")
    return out


def scan_text(cip: str, text: str) -> list[DriftHit]:
    """Return co-occurrence hits: same section asserted 'unchanged' AND modified."""
    unchanged: dict[str, str] = {}
    for m in _UNCHANGED.finditer(text):
        for sec in _sections(m):
            unchanged.setdefault(sec, m.group(0).strip())

    hits: list[DriftHit] = []
    if not unchanged:
        return hits
    for m in _MODIFY.finditer(text):
        for sec in _sections(m):
            if sec in unchanged and sec != "whitepaper":
                hits.append(
                    DriftHit(
                        cip=cip,
                        section=sec,
                        unchanged_line=unchanged[sec],
                        modify_line=m.group(0).strip(),
                    )
                )
    return hits


def scan_corpus(cips_dir: Path = COWBOY_CIPS) -> list[DriftHit]:
    hits: list[DriftHit] = []
    if not cips_dir.exists():
        return hits
    for path in sorted(cips_dir.glob("cip-*.md")):
        hits.extend(scan_text(path.stem, path.read_text(encoding="utf-8", errors="replace")))
    return hits
