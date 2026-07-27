# Cowboy-Pack Drift Board — spec vs. verified code

> This is **not** a concept page (no `concept_id` frontmatter — `parse_concept_page`
> skips it as `NotAConceptPage`, so it never appears in the concept tree). It is a
> companion reference for the cowboy domain pack: the "spec says X, code is Y"
> knowledge that reviewers most need when a PR touches money, consensus, or
> addresses.

Every **verified code value** in the tables below was re-read from the current
`node/` workspace (and, for `VerificationMode`, from the `cowboy-protocol-codec`
git rev that `node/Cargo.lock` pins: `28a5787…`). It is **not** copied from the
`2026-04-15` amendment — several values have drifted *further* than the amendment
recorded, and one drift the amendment flagged has since been *resolved*. When in
doubt, the authority order is **code > amendment > CIP > whitepaper**.

Each row names the `concept_id` it belongs to (must match a page in this pack).
`status` is one of:

- **live** — spec and current code still disagree.
- **resolved** — spec and current code now AGREE; kept as an audit trail.
- **amendment-stale** — the code has moved past what the 2026-04-15 amendment
  recorded; the amendment value is no longer the code value.

Sources: `refs/analysis/2026-04-15_documentation_amendments.md`,
`refs/wiki/drift.md`.

---

## High severity — money & consensus constants

| # | concept_id | Spec says (source) | Verified current code | Code location | Status |
|---|-----------|--------------------|-----------------------|---------------|--------|
| 1 | `dual-gas-model` | `BLOCK_CYCLES_TARGET = 10,000,000` (CIP-3 §2.2, WP §4.3) | **`20,000,000`** | `node/types/src/constants.rs:82` | **live** |
| 2 | `dual-gas-model` | `BLOCK_CELLS_TARGET = 500,000` (CIP-3 §2.2, WP §4.3) | **`4,000,000`** | `node/types/src/constants.rs:86` | **live** |
| 3 | `basefee` | Basefee update `α = 8`, linear `bf·(1+δ·(U−T)/T)`, δ = 12.5% (WP §4.2 / §17.8) | Geometric update, **`BASEFEE_ALPHA = 96`**, **`BASEFEE_MAX_CHANGE_DENOM = 96`**; change clamped to `basefee/DENOM` | `node/types/src/constants.rs:114,118`; `node/execution/src/basefee.rs:99-119` | **live** |
| 4 | `basefee` | `MIN_BASEFEE = 1` (WP) | **`MIN_BASEFEE = 10_000`** (u128); `MAX_BASEFEE = 1e24` | `node/types/src/constants.rs:140,144` | **live** |
| 5 | `system-actors` | WP §9 / CIP-2 give conflicting `0x01/0x03/0x06` roles; workspace CLAUDE.md lists `0x91–0x95` | Canonical map `0x01–0x1E`: `RUNNER_REGISTRY=0x01, JOB_DISPATCHER=0x02, RESULT_VERIFIER=0x03, SECRETS_MANAGER=0x04, TEE_VERIFIER=0x05, DUAL_BASEFEE=0x06, ENTITLEMENT_REGISTRY=0x07, TREASURY=0x08, GOVERNANCE=0x09, STORAGE_MANAGER=0x0A, RELAY_REGISTRY=0x0B, SESSION_ACTOR=0x0C, STREAM_KEY_MANAGER=0x0D, ROUTE_REGISTRY=0x0E, GATEWAY_REGISTRY=0x0F, RECEIPT_REGISTRY=0x10, VALIDATOR_SET=0x11, PAYMENT_GATE=0x12, CONTAINER_REGISTRY=0x13, INTENT_SETTLEMENT=0x14, BANK_ACTOR=0x16, EVENT_SUBSCRIPTION=0x1D, TRADING_POST=0x1E`. The `0x91–0x95` addresses do not exist. | `node/runner/src/system_actors.rs:32-83` | **live** + **amendment-stale** (amendment only recorded `0x01–0x0B`) |
| 6 | `runner-lifecycle` | `stake ≥ max(10,000 CBY, 1.5 × declared_max_job_value)` (WP §5.2) **vs** `stake ≥ 10 × avg_job_value` (WP §17.7) | `MIN_STAKE_CBY_WEI = 10,000 × 10⁹`; multiplier **`3/2` (= 1.5×)** via `STAKE_JOB_MULTIPLIER_NUM/DENOM` | `node/runner/src/types.rs:39,42-43`; `node/execution/src/runner/registry.rs` | **WP §5.2 resolved / WP §17.7 live** (10× formula is not in code) |
| 7 | `timer-mechanism` | CIP-1 §3: fire timers **then** execute transactions | Transactions execute first (list order), then due timers deliver at end-of-block | `node/storage/src/speculative.rs:496-505` (step 4 txs → step 9 timers) | **live vs CIP-1** (WP / CIP-5 order is correct) |

---

## Mid severity — costs, enums, budgets

| # | concept_id | Spec says (source) | Verified current code | Code location | Status |
|---|-----------|--------------------|-----------------------|---------------|--------|
| 8 | `gas` | Transfer instruction: `21,000` cycles / `0` cells (WP §17.2) | **`5,000` cycles / `500` cells** | `node/execution/src/gas.rs:223-224` (`transfer_cycles` / `transfer_cells`) | **live** |
| 9 | `runner-verification` | WP §5 lists **4** modes (TEE Attestation / Majority Vote / ZK-Proof / Economic Bond) | **6 variants**: `None(0), EconomicBond(1), MajorityVote(2), StructuredMatch(3), Deterministic(4), SemanticSimilarity(5)`. ZK-Proof mode does not exist; `StructuredMatch` + `SemanticSimilarity` are code-only additions. | `cowboy-protocol-codec` (rev `28a5787`) `crates/cowboy-protocol-codec/src/job_spec/types.rs:728`, re-exported via `cowboy_types` → `node/runner/src/types.rs:15` | **live** |
| 10 | `timer-mechanism` | No normative per-block / per-timer cycle budget in CIP-1 / CIP-5 | Block timer lane budget **`LANE_TIMER_CYCLES = 8,888,890`**; single-fire cap **`TIMER_CYCLES_LIMIT = 550,000`** (cells cap same) | `node/types/src/constants.rs:97,446,518` | **live** (documentation gap) |
| 11 | `gas` | CIP-20: token transfer/receive hook is capped at `50,000` cycles, enforced | `TOKEN_HOOK_MAX_CYCLES = 50,000` (and cells) is now **enforced** — sub-limit pushed before hook, overrun errors out (was "declared but not enforced" in the 2026-04-15 amendment §六·补) | `node/execution/src/gas.rs:380-382`; `node/execution/src/pvm_executor.rs:1516-1522`; `node/execution/src/execution/actor_instruction.rs:305,330` | **resolved** (spec ↔ code now agree; amendment §六·补 is stale) |
| 12 | `route-registry` | CIP-16 names `ROUTE_REGISTRY = 0x0D` | Code uses **`0x0E`** — `0x0D` was already taken by the CIP-7 `STREAM_KEY_MANAGER`; code comment reconciles the spec | `node/runner/src/system_actors.rs:57-62` | **live** |

---

## Notes for reviewers

- **Item 5 (system actors)** is the single most load-bearing row: the address map
  in the 2026-04-15 amendment (`0x01–0x0B`) is now stale — the code carries a much
  larger set through `0x1E`. Always verify an address against
  `node/runner/src/system_actors.rs`, not the amendment or workspace CLAUDE.md.
- **Item 11** shows a drift the amendment recorded that has since flipped to
  agreement: the CIP-20 hook cap is genuinely enforced now. Treat the amendment as
  a historical snapshot, not current truth.
- Items 6 and 9 are cases where the **whitepaper contradicts itself or the code
  extended the design**; the code value is authoritative.
