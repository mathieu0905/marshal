"""SYS_ opcode spec<->codec reconciliation check (COW-2399 item 3).

The opcode analog of `system_actor_addrmap`. System-instruction opcodes are the
chain's wire-format contract: the deployed codec assigns each `SystemInstruction`
a `pub const SYS_<NAME>: u8 = <N>` in `cowboy-protocol-codec`, and the cowboy spec
corpus (WP + CIPs) cites those opcodes in prose (`opcode 101`). Two recurring
hazard classes motivate this guard:

  (1) **Opcode collision** — two SYS_ names mapping to the same byte shadow each
      other's decode arm = consensus break (escape
      esc-20260608-cip12-cip16-opcode-collision; prior COW-1293 101<->SYS_RAS).
      The deployed-side uniqueness gate here is hard.
  (2) **Spec<->code drift** — a CIP citing `opcode N` the codec never deploys (or
      vice versa). The spec-side parser anchors strictly on the explicit
      `opcode <N>` keyword; bare markdown table cells (gas costs, exit codes,
      rate limits) are deliberately NOT swept in. Name-level reconciliation is a
      skeleton until the spec parser is hardened (mirrors how the addrmap parser
      was bootstrapped before flipping from xfail to a hard gate).

Reads from fixed git refs (not the working tree) so the check is deterministic
regardless of which branch the local repos sit on.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

WORKSPACE = Path("/home/ubuntu/workspace")
COWBOY_DOCS = WORKSPACE / "cowboy" / "docs"
COWBOY_REPO = WORKSPACE / "cowboy"
PROTOCOL_REPO = WORKSPACE / "cowboy-protocol"
CODEC_RS = PROTOCOL_REPO / "crates" / "cowboy-protocol-codec" / "src" / "instruction.rs"
# The codec crate is the wire-format source of truth for opcodes. cowboy-protocol
# has no devnet branch (unlike node) — read from `main`.
CODEC_REF = "main:crates/cowboy-protocol-codec/src/instruction.rs"

# Deployed const form: `pub const SYS_<NAME>: u8 = <N>;`. Scoped to the SYS_
# prefix on purpose — TX_CATEGORY_*/ACTOR_*/LIB_* are separate opcode namespaces
# whose values legitimately overlap the SYS_ range.
_SYS_CONST = re.compile(r"pub const (SYS_[A-Z0-9_]+)\s*:\s*u8\s*=\s*(\d+)\s*;")
# Reliable spec signal: the explicit `opcode <N>` keyword (optional backticks).
# Bare `| N |` table cells are NOT matched — in the corpus those are gas costs,
# exit codes, and rate limits far more often than opcodes.
_SPEC_OPCODE = re.compile(r"opcode\s*`?(\d{1,3})`?", re.IGNORECASE)


def _read_at_ref(repo: Path, ref_path: str, fallback: Path) -> str:
    """`git show <ref>:<path>` from `repo`, falling back to the working tree."""
    try:
        return subprocess.run(
            ["git", "-C", str(repo), "show", ref_path],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except Exception:
        return fallback.read_text(errors="replace")


def parse_deployed_opcodes(text: str) -> dict[str, int]:
    """`SYS_<NAME> -> opcode` for every `pub const SYS_<NAME>: u8 = <N>` in `text`."""
    return {m.group(1): int(m.group(2)) for m in _SYS_CONST.finditer(text)}


def deployed_opcodes_in_code() -> dict[str, int]:
    """Deployed SYS_ opcodes, read from the canonical `cowboy-protocol` codec ref."""
    return parse_deployed_opcodes(_read_at_ref(PROTOCOL_REPO, CODEC_REF, CODEC_RS))


def find_opcode_collisions(deployed: dict[str, int]) -> dict[int, set[str]]:
    """opcode -> set of SYS_ names mapped to it (collision iff >1)."""
    by_op: dict[int, set[str]] = {}
    for name, op in deployed.items():
        by_op.setdefault(op, set()).add(name)
    return {op: names for op, names in by_op.items() if len(names) > 1}


def spec_cited_opcodes(text: str | None = None) -> set[int]:
    """Opcodes explicitly cited as `opcode <N>` across the cowboy spec corpus.

    Pass `text` to parse a single document (used in tests); omit it to scan the
    whole `cowboy/docs` tree on disk.
    """
    if text is not None:
        return {int(m.group(1)) for m in _SPEC_OPCODE.finditer(text)}
    cited: set[int] = set()
    for md in sorted(COWBOY_DOCS.rglob("*.md")):
        cited |= {
            int(m.group(1)) for m in _SPEC_OPCODE.finditer(md.read_text(errors="replace"))
        }
    return cited


def find_spec_opcodes_not_in_code(cited: set[int], deployed: dict[str, int]) -> set[int]:
    """Opcodes the spec cites that no deployed SYS_ constant assigns."""
    return cited - set(deployed.values())
