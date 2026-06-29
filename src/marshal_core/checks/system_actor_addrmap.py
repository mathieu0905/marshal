"""System-actor address-map consistency check.

Permanent guard spawned by escape `esc-20260605-wp-0x0d-addrmap` (whitepaper PR
cowboyinc/cowboy#150 assigned `0x0D = Stream Key Manager`, contradicting CIP-7 /
CIP-2 / CIP-28 which place STREAM_KEY_MANAGER at `0x12` and `0x0D = ROUTE_REGISTRY`,
and citing `system_actors.rs:40` which does not define `0x0D` — code ends at `0x0C`).

The check parses every system-actor `address -> name` table across the cowboy spec
corpus and the node source, then asserts:

  (1) **No collision** — within a single canonical-allocation context, an address
      maps to exactly one actor name across the whole corpus.
  (2) **No false code citation** — any row tagged "code-deployed" or citing
      `system_actors.rs:<line>` resolves to a real `Address::from_low_u64(0x..)`
      constant actually present in `node/runner/src/system_actors.rs`.

NOTE (skeleton): the row parser below is intentionally minimal — it recognizes the
common `| 0xNN | Name ... |` markdown row shape. Implementers should harden the
parser (handle per-CIP "spec-only vs code-deployed" framing, revision tags like
"r2", and the `0x1D` virtual/intercepted actors which are legitimately not in
`system_actors.rs`) before flipping this from xfail to a hard gate. The known
`0x0D` collision MUST fail until the corpus is reconciled.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

WORKSPACE = Path("/home/ubuntu/workspace")
COWBOY_DOCS = WORKSPACE / "cowboy" / "docs"
NODE_REPO = WORKSPACE / "node"
COWBOY_REPO = WORKSPACE / "cowboy"
SYSTEM_ACTORS_RS = NODE_REPO / "runner" / "src" / "system_actors.rs"
# node's system-actor registry is the source of truth (WP §9.1 note 1). Read it
# from a fixed ref rather than the working tree — the deployed band depends on
# the *branch*, and devnet leads main (e.g. TRADING_POST 0x1E lands on devnet
# first). Pinning to the local checkout makes the check non-deterministic: the
# same drift class COW-2399 is meant to catch.
NODE_REF = "origin/devnet:runner/src/system_actors.rs"
WP_REF = "origin/main:docs/whitepaper/cowboy-technical-whitepaper.md"

# Addresses that are virtual / intercepted in pvm_host and legitimately NOT a
# deployed constant in system_actors.rs (do not flag as false code citation).
VIRTUAL_ADDRS = {0x1D}

# Corpus-wide CIP-table row (backtick or bare). Kept narrow on purpose: the
# wider the match, the more unrelated `| 0xNN | name |` tables (state-key
# prefixes, message-type ids) it sweeps in as false system-actor rows.
_ROW = re.compile(r"\|\s*`?(0x[0-9A-Fa-f]{1,2})`?\s*\|\s*([^|]+?)\s*\|")
# The WP §9.1 table uses bold address cells (`**0x11**`). A backtick-only regex
# was blind to the entire authoritative table — the one table the deployed↔table
# reconciliation most needs (COW-2399 item 2). Used ONLY against the WP file, so
# the broader match doesn't pollute the corpus-wide collision scan above.
_WP_ROW = re.compile(
    r"\|\s*(?:\*\*|`)?\s*(0x[0-9A-Fa-f]{1,2})\s*(?:\*\*|`)?\s*\|\s*(?:\*\*)?\s*([^|*]+?)\s*(?:\*\*)?\s*\|"
)
_RS_CONST = re.compile(r"Address::from_low_u64\((0x[0-9A-Fa-f]+)\)")
_CODE_DEPLOYED = re.compile(r"code-deployed|system_actors\.rs:\d+", re.IGNORECASE)


def _read_at_ref(repo: Path, ref_path: str, fallback: Path) -> str:
    """`git show <ref>:<path>` from `repo`, falling back to the working tree.

    Reading a fixed ref (not the checked-out tree) makes the check deterministic
    regardless of which branch the local repo happens to be on.
    """
    ref, _, _path = ref_path.partition(":")
    try:
        return subprocess.run(
            ["git", "-C", str(repo), "show", ref_path],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except Exception:
        return fallback.read_text(errors="replace")


@dataclass(frozen=True)
class Row:
    addr: int
    name: str
    source: str  # "file:line"
    claims_code_deployed: bool


def deployed_addresses_in_code() -> set[int]:
    """Real `0x..` constants defined in node `runner/src/system_actors.rs`,
    read from the canonical `origin/devnet` ref (not the working tree)."""
    text = _read_at_ref(NODE_REPO, NODE_REF, SYSTEM_ACTORS_RS)
    return {int(m.group(1), 16) for m in _RS_CONST.finditer(text)}


def wp_table_addresses() -> set[int]:
    """System-actor addresses listed in the WP §9.1 authoritative table.

    Per WP §9.1 note 1 the table MUST track the implementation registry, so this
    is the set every code-deployed address is required to appear in.
    """
    text = _read_at_ref(
        COWBOY_REPO, WP_REF, COWBOY_DOCS / "whitepaper" / "cowboy-technical-whitepaper.md"
    )
    addrs: set[int] = set()
    for line in text.splitlines():
        m = _WP_ROW.match(line.strip())
        if m:
            addr = int(m.group(1), 16)
            if addr <= 0x1F:
                addrs.add(addr)
    return addrs


def find_deployed_missing_from_wp_table() -> set[int]:
    """Code-deployed system-actor addresses absent from the WP §9.1 table.

    A code-reserved/deployed address that the authoritative table does not list
    is a table-tracking violation (WP §9.1 note 1). Example caught by this guard:
    `TRADING_POST 0x1E` is defined on node devnet but omitted from the WP table
    (COW-2399 item 2). Virtual/intercepted addresses are exempt.
    """
    return deployed_addresses_in_code() - wp_table_addresses() - VIRTUAL_ADDRS


def parse_spec_rows() -> list[Row]:
    rows: list[Row] = []
    for md in sorted(COWBOY_DOCS.rglob("*.md")):
        for i, line in enumerate(md.read_text(errors="replace").splitlines(), 1):
            m = _ROW.match(line.strip())
            if not m:
                continue
            try:
                addr = int(m.group(1), 16)
            except ValueError:
                continue
            # Only the single-byte system-actor band; skip storage-key tables etc.
            if addr > 0x1F:
                continue
            name = m.group(2).strip()
            rows.append(
                Row(
                    addr=addr,
                    name=name,
                    source=f"{md.relative_to(WORKSPACE)}:{i}",
                    claims_code_deployed=bool(_CODE_DEPLOYED.search(line)),
                )
            )
    return rows


def find_collisions(rows: list[Row]) -> dict[int, set[str]]:
    """address -> set of distinct actor-name stems mapped to it (collision if >1)."""
    # TODO(impl): canonicalize names (strip "(CIP-N ...)", revision tags) so that
    # "Stream Key Manager" and "STREAM_KEY_MANAGER" count as one. Until then,
    # callers should compare on a normalized stem.
    by_addr: dict[int, set[str]] = {}
    for r in rows:
        stem = re.split(r"[(\[]", r.name)[0].strip().lower().replace("_", " ")
        by_addr.setdefault(r.addr, set()).add(stem)
    return {a: names for a, names in by_addr.items() if len(names) > 1}


def find_false_code_citations(rows: list[Row], deployed: set[int]) -> list[Row]:
    return [
        r
        for r in rows
        if r.claims_code_deployed and r.addr not in deployed and r.addr not in VIRTUAL_ADDRS
    ]
