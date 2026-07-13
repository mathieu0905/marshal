#!/usr/bin/env python3
"""Assemble EMBED payloads and emit self-contained runnable workflow scripts.

Keeps the ~45k-token closure+diff OUT of the orchestrator context by embedding
them directly into the .js files (prepended as `const EMBED = {...}`).
"""
import json
import os
import sys

POC = os.path.dirname(os.path.abspath(__file__))


def rd(p):
    with open(os.path.join(POC, p), encoding="utf-8") as f:
        return f.read()


closure = rd("closure.md")
diff = rd("diff.patch")
base_lenses = json.loads(rd("base_lenses.json"))
ratchet = json.loads(rd("ratchet_lenses.json"))["lenses"]
# strip ratchet lenses down to {name, prompt}
ratchet = [{"name": l["name"], "prompt": l["prompt"]} for l in ratchet]


def emit(out_name, logic_file, embed):
    logic = rd(logic_file)
    # meta export MUST stay the first statement; inject EMBED right after meta's
    # closing brace (first line-start `}` closes the meta object literal).
    marker = "\n}\n"
    i = logic.index(marker) + len(marker)
    banner = "\nconst EMBED = " + json.dumps(embed, ensure_ascii=False) + ";\n"
    out = logic[:i] + banner + logic[i:]
    with open(os.path.join(POC, out_name), "w", encoding="utf-8") as f:
        f.write(out)
    print(f"wrote {out_name}: {len(out)} bytes  (closure={len(closure)}b diff={len(diff)}b)")


common = {"closure": closure, "diff": diff, "baseLenses": base_lenses, "ratchetLenses": ratchet}

# calibration: cheap subset, small caps — validate pipeline + measure per-agent cost
emit("deep_run_calib.js", "deep_review.js", {
    **common,
    "lensSubset": ["determinism", "ratchet:state-consensus"],
    "maxHypPerLens": 3, "globalHypCap": 6, "proveEffort": "high",
})

# full deep run: all lenses, realistic caps
emit("deep_run_full.js", "deep_review.js", {
    **common,
    "maxHypPerLens": 6, "globalHypCap": 30, "proveEffort": "high",
})

# regular baseline: all base lenses, diff-only single pass
emit("regular_run.js", "regular_review.js", {
    "diff": diff, "baseLenses": base_lenses, "effort": "medium",
})

# calibration regular (matched subset for fair per-agent comparison)
emit("regular_run_calib.js", "regular_review.js", {
    "diff": diff, "baseLenses": base_lenses,
    "lensSubset": ["determinism"], "effort": "medium",
})

print("\ncounts: base_lenses=%d  ratchet_lenses=%d" % (len(base_lenses), len(ratchet)))
