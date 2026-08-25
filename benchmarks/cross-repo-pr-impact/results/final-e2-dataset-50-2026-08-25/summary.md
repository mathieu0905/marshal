# Verification result

- admitted strict E2 cases: **50**
- existing execution cases normalized and audited: **46**
- new three-arm replays: **4**
- required arm direction: **A0 pass / A1 fail / A2 pass**
- machine-parsed arm directions: **50/50**
- declaration-only arm directions: **0/50**
- known rejection retained: **Terser -> Preconstruct**
- unique source-change families: **40**
- proposed split: **30 development / 10 evaluation / 10 holdout**
- source-change families crossing the proposed split: **0**

The validator derives all 50 directions from structured evidence rather than accepting the index declaration. The four new replays all returned `0/1/0` and reproduced their target-specific A1 signatures. The Terser Assetgraph/UI5 cases also have `0/1/0` process exits in each of three retained repetitions. The final index contains exactly 50 unique case IDs and 50 unique source-family/target relation keys.

The result closes the 50-case E2 collection objective. Further collection for A3, complete negative space, or four-arm packages is intentionally stopped. This remains a visible-label development/diagnostic package rather than a blind holdout release.
