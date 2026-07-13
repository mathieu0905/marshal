# Deep-Review PoC harness (node PR#936)

Reproducible artifacts for the deep-vs-regular calibration. Results write-up:
`../../specs/2026-07-13-deep-review-poc-results.md`.

- `deep_review.js` / `regular_review.js` — Workflow logic (read args or EMBED fallback).
- `base_lenses.json` — 6 base review lenses.
- `build_args.py` — assembles EMBED payload (closure+diff+lenses) into runnable
  `*_run_*.js` (payload embedded so it never enters orchestrator context).
- `deep_calib_result.json` / `regular_result.json` — the two runs' findings.
- `closure-evidence.md` — the change-closure bundle fed as the shared cached prefix.

Rebuild inputs: `gh pr diff 936 -R cowboyinc/node > diff.patch`;
`marshal_core.cli ratchet-lenses --max-lenses 5 --samples 2 > ratchet_lenses.json`;
then `python build_args.py` and run each `*_run_*.js` via the Workflow tool.
