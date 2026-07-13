# Marshal deep-review harness (optional measured path)

Reusable Workflow logic for `/marshal deep` when you want deterministic runs +
real token accounting (`budget.spent()`). The primary deep flow is orchestrated
directly by the skill brain (see `../references/deep-review-flow.md`); these are
for the measured/batch path.

- `deep_review.js` — closure → scout(hypotheses) → dedup/cap → prove(trigger-or-refute).
  Reads `args` = {closure, diff, baseLenses, ratchetLenses, lensSubset?, maxHypPerLens,
  globalHypCap, proveEffort}. baseLenses/ratchetLenses come from
  `cli review-lenses --repo <r> --paths … --ratchet-top <N>` (fields base/ratchet).
- `regular_review.js` — single-pass baseline (diff-only), for A/B token comparison.

Lenses: `cli review-lenses` (pack review_plan + ratchet). Closure: a context-builder
subagent (see deep-review-flow.md §2). PoC that validated this: `docs/superpowers/poc/`.
