# Change-Closure Bundle — node PR#936 (COW-2435 / TOB-COWBOY-18)

**PR title (inferred from diff):** Add per-event `emitter` attribution to events — event tuples become `(emitter, topic, data)` and the emitter is committed into `logs_root`, `bloom`, and the receipt/RLP encodings; events are persisted to each true emitter's actor-log (flag-day, consensus-relevant).
**PR head commit:** `4a9c6ac4`. All code below copied verbatim from the PR-head worktree.

## Changed files (one-line purpose)

Priority (execution/ + storage/ — full bodies below):
- `storage/src/types.rs` — `ActorEvent` gains `emitter: Address`; `compute_logs_root` / `compute_bloom` / `TransactionReceipt` codec + `rlp_encode` all commit the emitter. **Core commitment surface.**
- `storage/src/speculative.rs` — new `system_event_emitter()` helper + the receipt-build/commit loop that normalizes system/library emitters and persists events grouped by emitter. **Single authoritative normalization point.**
- `execution/src/pvm_host.rs` — `PvmExecutionContext.events` becomes `(Address,String,Vec<u8>)`; `emit_event` / `fire_sync_subscribers` / `upgrade_self` tag events with `self.ctx.actor_address` (the callee on a nested call). **Where the true per-event emitter is stamped.**
- `execution/src/pvm_executor.rs` — `ExecutionSideEffects.events` retyped to carry emitter.
- `execution/src/execution/event_fire.rs` — `execute_event_fire_batch` tags `cip29.subscription_expired`/`cip29.async_fire` with their emitter.
- `execution/src/execution/library_instruction.rs` — `execute_publish_library`/`execute_remove_library` tag CIP-26 events with `*sender`.
- `execution/src/execution/actor_instruction.rs` — `execute_actor_instruction` / `execute_actor_handler_impl` return types retyped; deferred-tx `deferred_tx.created` events tagged with `actor_address_clone`.
- `execution/src/execution/transaction.rs` — `execute_transaction` / `execute_deferred_transaction` map drained `system_events` to `(tx.from, …)` placeholder emitter; deferred lifecycle events tagged with `tx.from`.
- `execution/src/execution/transaction_executor_impl.rs` — `TransactionExecutor` impl return-type retyping (mechanical).
- `storage/src/traits.rs` — `TransactionExecutor` trait return-type retyping (mechanical).
- `storage/src/cbss_reshare_overflow.rs` / `storage/src/accounts.rs` — set `emitter` on constructed `ActorEvent`s (CBSS_SYSTEM_ACTOR / test).
- `execution/src/execution/tests.rs`, `storage/src/{lib,state_invariants,state_value}.rs` — test destructuring/construction updates (mechanical).

Non-priority (cli / client / indexer / rpc — summarized at end, bodies omitted):
- `cli/src/commands.rs`, `client/src/rpc.rs`, `indexer/src/{db,json,lib}.rs`, `rpc/src/{handlers/chain,responses,rpc}.rs`.

---

# storage/src/types.rs

```rust
// storage/src/types.rs::ActorEvent (struct at PR head)
/// A single event emitted by an actor during transaction execution.
///
/// COW-2435 (TOB-COWBOY-18): `emitter` is the address of the actor that actually
/// emitted the event — the current actor at `emit_event` time, i.e. the callee
/// on a nested call, not the tx-level actor. It is part of the committed encoding
/// (below) and of `compute_logs_root`, so the receipt's `logs_root` binds it:
/// address-scoped log indexing attributes nested-call events correctly, and
/// off-chain consumers can independently verify an actor-log response contains
/// only events emitted by the requested actor.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ActorEvent {
    pub block_height: u64,
    pub tx_hash: Sha256Digest,
    pub emitter: Address,
    pub topic: String,
    pub data: Vec<u8>,
}

impl Write for ActorEvent {
    fn write(&self, writer: &mut impl BufMut) {
        self.block_height.write(writer);
        self.tx_hash.write(writer);
        self.emitter.write(writer);
        self.topic.as_bytes().write(writer);
        self.data.write(writer);
    }
}

impl Read for ActorEvent {
    type Cfg = ();

    fn read_cfg(reader: &mut impl Buf, _: &Self::Cfg) -> Result<Self, commonware_codec::Error> {
        let block_height = u64::read(reader)?;
        let tx_hash = Sha256Digest::read(reader)?;
        let emitter = Address::read(reader)?;
        let topic_bytes = Vec::<u8>::read_cfg(reader, &(RangeCfg::from(0..=256), ()))?;
        let topic = String::from_utf8(topic_bytes).map_err(|_| {
            commonware_codec::Error::Invalid("ActorEvent", "invalid topic encoding")
        })?;
        let data = Vec::<u8>::read_cfg(reader, &(RangeCfg::from(0..=65536), ()))?;
        Ok(Self {
            block_height,
            tx_hash,
            emitter,
            topic,
            data,
        })
    }
}

impl EncodeSize for ActorEvent {
    fn encode_size(&self) -> usize {
        self.block_height.encode_size()
            + self.tx_hash.encode_size()
            + self.emitter.encode_size()
            + self.topic.as_bytes().encode_size()
            + self.data.encode_size()
    }
}
```
Diff: inserted `emitter: Address` field (3rd, after `tx_hash`) and wrote/read/sized it in the same position across all three codec impls.

```rust
// storage/src/types.rs::compute_logs_root (fn at PR head)
/// Compute the keccak256 root over all events emitted by a transaction (#103).
///
/// Encoding: 4-byte event count, then for each event:
///   4-byte topic length, topic bytes, 4-byte data length, data bytes.
///
/// COW-2435 (TOB-COWBOY-18): each event's `emitter` (the actor that emitted it,
/// 20 bytes) is committed alongside its topic and data, so the receipt's
/// `logs_root` binds who emitted each event — nested-call events are attributed
/// to their true emitter and off-chain consumers can verify actor-log responses.
pub fn compute_logs_root(events: &[(Address, String, Vec<u8>)]) -> Sha256Digest {
    let mut buf = Vec::new();
    buf.extend_from_slice(&(events.len() as u32).to_be_bytes());
    for (emitter, topic, data) in events {
        buf.extend_from_slice(emitter.as_ref());
        buf.extend_from_slice(&(topic.len() as u32).to_be_bytes());
        buf.extend_from_slice(topic.as_bytes());
        buf.extend_from_slice(&(data.len() as u32).to_be_bytes());
        buf.extend_from_slice(data);
    }
    Sha256Digest::from(cowboy_types::keccak256(&buf))
}
```
Diff: signature `&[(String, Vec<u8>)]` → `&[(Address, String, Vec<u8>)]`; prepends the 20-byte `emitter` (no length prefix) before each event's framed topic/data. Golden vectors recomputed (see tests below).

```rust
// storage/src/types.rs::compute_bloom (fn at PR head)
/// Compute a 2048-bit (256-byte) Bloom filter over event emitters + topics (#90).
///
/// Inspired by EIP-2 Bloom (3 bit positions per item via keccak256), using
/// little-endian bit ordering within each byte. COW-2435: the emitter address is
/// bloomed too, so address-scoped log queries can be pre-filtered by emitter.
pub fn compute_bloom(events: &[(Address, String, Vec<u8>)]) -> [u8; 256] {
    let mut bloom = [0u8; 256];
    let mut set_bits = |item: &[u8]| {
        let hash = cowboy_types::keccak256(item);
        for i in 0..3 {
            let bit_index = u16::from_be_bytes([hash[i * 2], hash[i * 2 + 1]]) as usize % 2048;
            bloom[bit_index / 8] |= 1 << (bit_index % 8);
        }
    };
    for (emitter, topic, _data) in events {
        set_bits(topic.as_bytes());
        set_bits(emitter.as_ref());
    }
    bloom
}
```
Diff: refactored the per-topic bit-set into a `set_bits` closure and now blooms both `topic` and `emitter` (topic first, then emitter) for each event.

```rust
// storage/src/types.rs::TransactionReceipt (struct field at PR head — events)
    pub remaining_cells: u64,
    /// COW-2435: `(emitter, topic, data)` — the committing emitter is included so
    /// receipt consumers see who emitted each event.
    pub events: Vec<(Address, String, Vec<u8>)>,
```

```rust
// storage/src/types.rs::<Write for TransactionReceipt>::write (events portion at PR head)
        (self.events.len() as u32).write(writer);
        for (emitter, topic, data) in &self.events {
            emitter.write(writer);
            topic.as_bytes().write(writer);
            data.write(writer);
        }
```

```rust
// storage/src/types.rs::<Read for TransactionReceipt>::read_cfg (events portion at PR head)
        let mut events = Vec::with_capacity(events_count as usize);
        for _ in 0..events_count {
            let emitter = Address::read(reader)?;
            let topic_bytes = Vec::<u8>::read_cfg(reader, &(RangeCfg::from(0..=256), ()))?;
            let topic = String::from_utf8(topic_bytes).map_err(|_| {
                commonware_codec::Error::Invalid("TransactionReceipt", "invalid event topic")
            })?;
            let data = Vec::<u8>::read_cfg(reader, &(RangeCfg::from(0..=1024 * 1024), ()))?;
            events.push((emitter, topic, data));
        }
```
Note: the receipt codec has NO version bump for the emitter prefix; `emitter` is read/written unconditionally in the events loop (flag-day). The trailing v2/v3 fields (`tx_type`, cumulative, `logs_root`, `bloom`, `post_tx_state_root`) still use the `has_remaining()` optional-suffix pattern.

```rust
// storage/src/types.rs::<EncodeSize for TransactionReceipt>::encode_size (events portion at PR head)
            + self.events
                .iter()
                .map(|(emitter, topic, data)| {
                    emitter.encode_size() + topic.as_bytes().encode_size() + data.encode_size()
                })
                .sum::<usize>()
```

```rust
// storage/src/types.rs::TransactionReceipt::rlp_encode (log-item portion at PR head)
        // Encode log entries: each is RLP([emitter, topic, data])
        let log_items: Vec<Vec<u8>> = self
            .events
            .iter()
            .map(|(emitter, topic, data)| {
                rlp::encode_list(&[
                    rlp::encode_bytes(emitter.as_ref()),
                    rlp::encode_bytes(topic.as_bytes()),
                    rlp::encode_bytes(data),
                ])
            })
            .collect();
        let logs = rlp::encode_list(&log_items);
```
Diff: each RLP log entry becomes a 3-element list `[emitter, topic, data]` (was `[topic, data]`).

Test-golden changes (`mod tests`): `logs_root_golden_vector_and_event_sensitivity` adds a `diff_emitter` sensitivity case and recomputes `GOLDEN`; `consensus_event_multi_topic_encoding_golden` prefixes every event with `em = Address::from_low_u64(0xEEEE)` and recomputes `GOLDEN_MULTI`. Both golden constants were changed (flag-day recompute).

---

# storage/src/speculative.rs

```rust
// storage/src/speculative.rs::system_event_emitter (NEW fn at PR head)
/// COW-2435 (TOB-COWBOY-18): the canonical emitter for a transaction's events
/// when the instruction is a SYSTEM or LIBRARY op. Those events are emitted by
/// Rust system code on behalf of a fixed actor (a system registry, the target of
/// an upgrade, or the library publisher), so all of the tx's events attribute to
/// that actor. Returns `None` for actor instructions: their events already carry
/// the true per-event emitter (the callee on a nested call) and must not be
/// normalized to the tx-level actor.
fn system_event_emitter(
    instruction: &cowboy_types::Instruction,
    tx_from: Address,
) -> Option<Address> {
    use cowboy_types::{Instruction, SystemInstruction};
    match instruction {
        Instruction::Actor(_) => None,
        Instruction::System(sys_inst) => match sys_inst.as_ref() {
            SystemInstruction::UpgradeActor { actor, .. } => Some(*actor),
            SystemInstruction::SetSecret(_)
            | SystemInstruction::UpdateSecretPolicy(_)
            | SystemInstruction::DeleteSecretVersion(_)
            | SystemInstruction::DeleteSecret(_)
            | SystemInstruction::RegisterCbssProxy(_)
            | SystemInstruction::DeregisterCbssProxy(_)
            | SystemInstruction::RotateCommittee(_)
            | SystemInstruction::SlashCbssProxy(_)
            | SystemInstruction::SubmitReleaseReceipt(_)
            | SystemInstruction::RequestAccountDkg(_)
            | SystemInstruction::RequestReshare(_)
            | SystemInstruction::FinalizeSecretVersion(_)
            | SystemInstruction::SubmitLivenessChallenge(_)
            | SystemInstruction::LivenessChallengeResponse(_)
            | SystemInstruction::ExpireLivenessChallenge(_)
            | SystemInstruction::ExpireDkgPending(_) => Some(CBSS_SYSTEM_ACTOR),
            SystemInstruction::TokenTransfer { .. }
            | SystemInstruction::TokenTransferFrom { .. }
            | SystemInstruction::TokenApprove { .. }
            | SystemInstruction::TokenMint { .. }
            | SystemInstruction::TokenBurn { .. }
            | SystemInstruction::TokenFreeze { .. }
            | SystemInstruction::TokenUnfreeze { .. }
            | SystemInstruction::TokenSetHook { .. }
            | SystemInstruction::TokenTransferOwnership { .. }
            | SystemInstruction::TokenTransferBatch { .. } => Some(TOKEN_REGISTRY_SYSTEM_ACTOR),
            _ => None,
        },
        // CIP-26 §3.3: library events attribute to the publisher's own log.
        Instruction::Library(_) => Some(tx_from),
        _ => None,
    }
}
```
This is the extracted/renamed version of the emitter-routing match that previously lived inline in the persist block of the commit loop (see the deleted inline `actor_addr` match in the diff). Behavior is identical to the old inline mapping, but it now runs BEFORE commitment so it also affects `logs_root`/`bloom`/receipt, not just persistence.

```rust
// storage/src/speculative.rs::execute_block_speculative (receipt-build + commit loop region at PR head)
// [Enclosing fn `execute_block_speculative` (starts ~line 454) is very large;
//  this is the per-tx receipt-build + event-commit region — the only part the
//  diff touches.]
        for (
            tx_index,
            (((tx, (cycles_used, cells_used, status, deferred_hashes, events)), pvm_gas), rd),
        ) in block
            .transactions
            .iter()
            .zip(execution_results.iter())
            .zip(pvm_per_instr_gases.iter().copied())
            .zip(tx_return_data.iter().cloned())
            .enumerate()
        {
            let tx_hash = Sha256Digest::from(tx.digest().0);
            let remaining_cycles = tx.cycles_limit.saturating_sub(*cycles_used);
            let remaining_cells = tx.cells_limit.saturating_sub(*cells_used);

            cumulative_cycles = cumulative_cycles.saturating_add(*cycles_used);
            cumulative_cells = cumulative_cells.saturating_add(*cells_used);

            // COW-2435 (TOB-COWBOY-18): normalize the emitter of system/library-
            // instruction events to their canonical system actor BEFORE the
            // commitment (`logs_root`) and append. Actor-instruction events keep
            // their per-event emitter (the true callee on a nested call). The
            // executor tags system/inline events with a placeholder emitter; this
            // is the single authoritative point that fixes them.
            let events: Vec<(Address, String, Vec<u8>)> =
                match system_event_emitter(&tx.instruction, tx.from) {
                    Some(canonical) => events
                        .iter()
                        .map(|(_, topic, data)| (canonical, topic.clone(), data.clone()))
                        .collect(),
                    None => events.clone(),
                };

            let (tx_type, tx_sub_type) = tx.instruction.tx_type();
            let receipt = TransactionReceipt {
                tx_hash,
                cycles_used: *cycles_used,
                cells_used: *cells_used,
                block_height: block.height.get(),
                block_hash,
                tx_index: tx_index as u32,
                status: status.clone(),
                deferred_tx_hashes: deferred_hashes.clone(),
                remaining_cycles,
                remaining_cells,
                events: events.clone(),
                tx_type,
                tx_sub_type,
                cumulative_cycles_used: cumulative_cycles,
                cumulative_cells_used: cumulative_cells,
                logs_root: compute_logs_root(&events),
                bloom: if events.is_empty() {
                    None
                } else {
                    Some(compute_bloom(&events))
                },
                post_tx_state_root: Sha256Digest([0u8; 32]),
                // CIP-3 §2.2.1 Phase 2a: populated from the executor's
                // side-channel (observe-only — NOT in the receipt codec, NOT
                // in `receipt_root` or consensus state).
                pvm_per_instr_gas: pvm_gas,
                // Handler return bytes for `ActorInstruction::ExecuteActor`
                // (observe-only — NOT in the receipt codec, NOT in
                // `receipt_root` or consensus state). Durable RPC surfacing
                // requires a non-merkleized auxiliary store.
                return_data: rd,
            };

            self.set_tx_receipt(tx_hash, receipt.clone()).await?;
            receipts.push(receipt);

            // COW-2435: persist events to each EMITTER's event log. `events` now
            // carries the true per-event emitter (actor emits keep the callee;
            // system/library emits were normalized to their canonical system
            // actor above), so group by emitter and append each group under its
            // own actor. Deterministic: BTreeMap iterates emitters in sorted order.
            if !events.is_empty() {
                let mut by_emitter: std::collections::BTreeMap<Address, Vec<ActorEvent>> =
                    std::collections::BTreeMap::new();
                for (emitter, topic, data) in &events {
                    by_emitter.entry(*emitter).or_default().push(ActorEvent {
                        block_height: block.height.get(),
                        tx_hash,
                        emitter: *emitter,
                        topic: topic.clone(),
                        data: data.clone(),
                    });
                }
                for (emitter, actor_events) in by_emitter {
                    if let Err(e) = self.append_actor_events(emitter, actor_events).await {
                        warn!("failed to persist actor events: {:?}", e);
                    }
                }
            }
            // ... (deferred-tx indexing continues below, unchanged) ...
```
Diff: (1) inserts the `system_event_emitter` normalization of `events` before the receipt is built; (2) `compute_logs_root`/`compute_bloom` now take `&events` (by ref); (3) replaces the old single-`actor_addr` inline routing match + single `append_actor_events` call with a `BTreeMap<Address, Vec<ActorEvent>>` grouping that appends each emitter's events under that emitter. The timer/CBSS-overflow `ActorEvent` constructions elsewhere in this file gained `emitter:` fields (CBSS_SYSTEM_ACTOR for reshare-overflow/DKG paths; `timer.actor_address` for `timer.expired` / `timer.cancelled_insufficient_funds` / `timer.dead_lettered` / `timer.fired`).

---

# execution/src/pvm_host.rs

```rust
// execution/src/pvm_host.rs::PvmExecutionContext (events field at PR head)
    // Events emitted during execution
    // Use Arc<Mutex<>> for shared mutability with Send trait support
    // This allows the Future to be Send-safe for async execution
    // Performance impact is minimal as these are only accessed during execution
    // COW-2435 (TOB-COWBOY-18): (emitter, topic, data). `emitter` is the actor
    // that emitted the event — the current actor at `emit_event` time, i.e. the
    // callee on a nested call — so events are attributed to and committed under
    // their true emitter, not the tx-level actor.
    pub events: std::sync::Arc<std::sync::Mutex<Vec<(cowboy_types::Address, String, Vec<u8>)>>>,
```

```rust
// execution/src/pvm_host.rs::PvmExecutionContext::clone_side_effects_refs (fn at PR head)
    #[allow(clippy::type_complexity)]
    pub fn clone_side_effects_refs(
        &self,
    ) -> (
        std::sync::Arc<std::sync::Mutex<Vec<(Address, String, Vec<u8>)>>>,
        std::sync::Arc<std::sync::Mutex<Vec<(Vec<u8>, Vec<u8>)>>>,
        std::sync::Arc<std::sync::Mutex<Vec<crate::pvm_executor::ScheduledTimer>>>,
        std::sync::Arc<std::sync::Mutex<Vec<(Address, Vec<u8>)>>>,
        std::sync::Arc<std::sync::Mutex<Vec<(Address, Vec<u8>, u64)>>>,
        std::sync::Arc<std::sync::Mutex<Vec<DeferredTxRequest>>>,
    ) {
        (
            self.events.clone(),
            self.outgoing_messages.clone(),
            self.scheduled_timers.clone(),
            self.cancelled_timers.clone(),
            self.extended_timers.clone(),
            self.deferred_tx_requests.clone(),
        )
    }
```
Diff: first tuple element retyped `Vec<(String,Vec<u8>)>` → `Vec<(Address,String,Vec<u8>)>`; added `#[allow(clippy::type_complexity)]`.

```rust
// execution/src/pvm_host.rs::CowboyHost::emit_event (fn at PR head)
    fn emit_event(&mut self, topic: &str, data: &[u8]) -> HostResult<()> {
        use cowboy_types::{MAX_EMITS_PER_TX, MAX_EVENT_DEPTH, MAX_EVENT_PAYLOAD_BYTES};

        self.deny_if_read_only()?;
        // COW-231: structured host-call trace.
        trace!(
            target: "pvm::host",
            syscall = "emit_event",
            actor = ?self.ctx.actor_address,
            topic,
            data_len = data.len(),
            "host call"
        );

        // ── Per-call validation ─────────────────────────────────────────────
        if data.len() > MAX_EVENT_PAYLOAD_BYTES {
            return Err(HostError::InvalidInput);
        }

        // ── Tx-local cap enforcement ────────────────────────────────────────
        if self.ctx.emit_count >= MAX_EMITS_PER_TX as u32 {
            return Err(HostError::EntitlementQuotaExceeded);
        }
        if (self.ctx.event_depth as u32) >= MAX_EVENT_DEPTH as u32 {
            return Err(HostError::EntitlementQuotaExceeded);
        }
        // EMIT_SAME_TOPIC_REENTRY = false: reject re-emit of an in-flight topic.
        let topic_bytes = topic.as_bytes().to_vec();
        if self.ctx.recently_emitted_topics.contains(&topic_bytes) {
            return Err(HostError::Forbidden);
        }

        // ── Charge cells for emit overhead + payload (legacy behavior) ─────
        // COW-1919 / CIP-29 §2.3: payload bytes are billed 1 cell/byte against
        // the emitter (same model as calldata) — no fixed overhead, topic not
        // billed as cells. (Was `50 + topic.len() + data.len()`.)
        let cells = data.len() as u64;
        self.ctx
            .gas_meters
            .cells
            .consume_tracked(cells, "emit_event", GasCategory::Messaging)
            .map_err(|_| HostError::OutOfGas)?;

        // ── Preserve the legacy event-log append (off-chain indexer ABI) ───
        // COW-2435: tag the event with its emitter (the current actor — the callee
        // on a nested call), so it is attributed to and committed under the true
        // emitter rather than the tx-level actor.
        let emitter = self.ctx.actor_address;
        self.ctx
            .events
            .lock()
            .unwrap()
            .push((emitter, topic.to_string(), data.to_vec()));

        // ── Increment counters + push topic stack frame ─────────────────────
        self.ctx.emit_count = self.ctx.emit_count.saturating_add(1);
        self.ctx.event_depth = self.ctx.event_depth.saturating_add(1);
        self.ctx.recently_emitted_topics.insert(topic_bytes.clone());

        // ── Read the bid-sorted subscription index for this (emitter, topic) ─
        let emitter_addr = self.ctx.actor_address;
        let index = block_on_store_future(
            self.ctx
                .store
                .get_event_sub_index(&emitter_addr, &topic_bytes),
        )
        .map_err(|_| HostError::StorageError)?;

        // Split into sync (top-K) and async (overflow). The index is already
        // sorted by (bid_inv, sub_height, sub_id) per Phase 1 T6.
        let k = cowboy_types::MAX_SYNC_FIRES_PER_TOPIC.min(index.entries.len());
        let (sync_entries, async_entries) = index.entries.split_at(k);

        // ── Sync-fire loop (Task 4 fills in the body) ──────────────────────
        self.fire_sync_subscribers(&emitter_addr, &topic_bytes, data, sync_entries)?;

        // ── Async-fire enqueue (Task 5 fills in the body) ──────────────────
        if !async_entries.is_empty() {
            self.enqueue_async_fires(&emitter_addr, &topic_bytes, data, async_entries)?;
        }

        // ── Pop topic frame + decrement depth ──────────────────────────────
        self.ctx.recently_emitted_topics.remove(&topic_bytes);
        self.ctx.event_depth = self.ctx.event_depth.saturating_sub(1);

        Ok(())
    }
```
Diff: the legacy log-append now pushes `(emitter, topic, data)` where `emitter = self.ctx.actor_address` (the current call frame's actor). `self.ctx.actor_address` is set to the callee when a nested `call_actor` swaps context (`switch_to_callee`/`restore_call_snapshot`), so nested-call emits carry the callee's address.

```rust
// execution/src/pvm_host.rs::CowboyHost::fire_sync_subscribers (bookkeeping-event region at PR head)
// [Enclosing fn spans ~1680–1766; only the bookkeeping-event push changed.]
            // Bookkeeping event for off-chain indexers (audit trail).
            // Format: 1-byte status (0=ok, 1=err) + 33-byte sub_id + 20-byte subscriber.
            let status_byte: u8 = if fire_result.is_ok() { 0 } else { 1 };
            let mut log_payload = Vec::with_capacity(54);
            log_payload.push(status_byte);
            log_payload.extend_from_slice(&entry.sub_id);
            log_payload.extend_from_slice(subscriber.as_ref());
            let emitter = self.ctx.actor_address;
            if let Ok(mut events) = self.ctx.events.lock() {
                events.push((emitter, "cip29.sync_fire".to_string(), log_payload));
            }
```
Diff: `cip29.sync_fire` bookkeeping event tagged with `self.ctx.actor_address` (the emitting actor whose emit triggered the sync fire).

```rust
// execution/src/pvm_host.rs::CowboyHost::upgrade_self (sys.upgrade.completed emit region at PR head)
// [Enclosing fn `upgrade_self` spans ~4102–4229; only the emit push changed.]
        // 6. Emit sys.upgrade.completed event
        let event_data = format!(
            "{{\"actor\":\"{}\",\"old_code_hash\":\"{}\",\"new_code_hash\":\"{}\"}}",
            hex::encode(self.ctx.actor.address.as_ref()),
            hex::encode(old_code_hash.as_ref()),
            hex::encode(new_code_hash.as_ref()),
        );
        let emitter = self.ctx.actor_address;
        if let Ok(mut events) = self.ctx.events.lock() {
            events.push((
                emitter,
                "sys.upgrade.completed".to_string(),
                event_data.into_bytes(),
            ));
        }
```
Diff: `sys.upgrade.completed` tagged with `self.ctx.actor_address`. (Note: for the EOA `UpgradeActor` system-instruction path, `system_event_emitter` in speculative.rs re-normalizes to the target `actor`, overriding this placeholder.)

---

# execution/src/pvm_executor.rs

```rust
// execution/src/pvm_executor.rs::ExecutionSideEffects (struct at PR head)
#[derive(Debug, Clone)]
pub struct ExecutionSideEffects {
    pub outgoing_messages: Vec<(Vec<u8>, Vec<u8>)>,
    pub scheduled_timers: Vec<ScheduledTimer>,
    /// `(caller_address, timer_id)` — caller is the actor whose call frame
    /// invoked `cancel_timer`. Captured at host-call time.
    pub cancelled_timers: Vec<(Address, Vec<u8>)>,
    /// Model B.6: `(caller_address, timer_id, new_expires_at)` triples
    /// staged by `extend_timer`. Flush verifies ownership and bound.
    pub extended_timers: Vec<(Address, Vec<u8>, u64)>,
    /// COW-2435: `(emitter, topic, data)` — emitter is the actor that emitted the
    /// event (the callee on a nested call), so events are attributed/committed
    /// under their true emitter.
    pub events: Vec<(Address, String, Vec<u8>)>,
}
```
Diff: `events` field retyped to include emitter.

---

# execution/src/execution/event_fire.rs

```rust
// execution/src/execution/event_fire.rs::execute_event_fire_batch (fn at PR head)
pub async fn execute_event_fire_batch<S: StateStore + Send>(
    store: &mut S,
    metadata: &[u8],
    block_height: u64,
    block_hash: &Digest,
    timestamp_ms: u64,
    origin_tx_hash: &Digest,
    gas_pool_cycles: u64,
    gas_pool_cells: u64,
) -> Result<(u64, u64, Vec<(cowboy_types::Address, String, Vec<u8>)>), ExecutionError>
where
    <S as StateStore>::Error: From<cowboy_storage::Error>,
{
    let origin = EmitOrigin::from_metadata_bytes(metadata).ok_or(ExecutionError::InvalidData)?;

    let mut pool_cycles = gas_pool_cycles;
    let mut pool_cells = gas_pool_cells;
    let mut events: Vec<(cowboy_types::Address, String, Vec<u8>)> = Vec::new();

    for sub_id in &origin.sub_ids {
        // Load EventSub. Missing → race (force-unsubscribed between emit and fire); skip.
        let mut sub = match store.get_event_sub(sub_id).await {
            Ok(Some(s)) => s,
            Ok(None) => continue,
            Err(e) => return Err(ExecutionError::StoreError(Box::new(e))),
        };

        // Zombie reap.
        if sub.gas_remaining < MIN_FIRE_COST {
            let _ = store
                .remove_index_entry(&sub.emitter_addr, &sub.topic, sub_id)
                .await;
            let _ = store.delete_event_sub(sub_id).await;
            continue;
        }

        // Cap the fire budget by both the sub's gas_remaining and what's left
        // in the defer tx's gas pool.
        let fire_cycles = sub.gas_remaining.min(pool_cycles);
        if fire_cycles < MIN_FIRE_COST {
            break; // pool exhausted; unfired subs stay registered for a future emit
        }
        let fire_cells = pool_cells;

        // Pre-flight: confirm the subscriber actor still exists. If it doesn't,
        // reap the sub — but leave an audit trail. COW-1149: a subscriber
        // deleted between the emit and the async fire used to be reaped
        // silently. Emit a `cip29.subscription_expired` event recording the
        // sub, the reason, and the unfired `gas_remaining` (the refund
        // obligation), mirroring the cip29.* bookkeeping events that off-chain
        // trackers reconcile (the deleted subscriber cannot receive an
        // on-chain credit, so the obligation is recorded for the sink).
        match store.get_actor(&sub.subscriber).await {
            Ok(Some(_)) => {}
            Ok(None) | Err(_) => {
                const REASON_ACTOR_DELETED: u8 = 0;
                // sub_id(33) ‖ subscriber(20) ‖ reason(1) ‖ refund_gas(8 LE) = 62 bytes
                let mut log_payload = Vec::with_capacity(33 + 20 + 1 + 8);
                log_payload.extend_from_slice(sub_id);
                log_payload.extend_from_slice(sub.subscriber.as_ref());
                log_payload.push(REASON_ACTOR_DELETED);
                log_payload.extend_from_slice(&sub.gas_remaining.to_le_bytes());
                events.push((
                    sub.emitter_addr,
                    "cip29.subscription_expired".to_string(),
                    log_payload,
                ));

                let _ = store
                    .remove_index_entry(&sub.emitter_addr, &sub.topic, sub_id)
                    .await;
                let _ = store.delete_event_sub(sub_id).await;
                continue;
            }
        };

        // Build a fresh PvmExecutionContext rooted at the subscriber. The
        // subscriber sees `sender = origin.emitter` (the emitter is the caller).
        let mut gas_meters = DualGasMeters::new(fire_cycles, fire_cells);
        let subscriber_addr = sub.subscriber;
        let emitter_addr = sub.emitter_addr;

        let (cycles_used, cells_used) = {
            let mut pvm_ctx = match PvmExecutionContext::new(
                subscriber_addr,
                block_height,
                *block_hash,
                *origin_tx_hash,
                emitter_addr,
                timestamp_ms,
                store,
                &mut gas_meters,
                None,
            )
            .await
            {
                Ok(ctx) => ctx,
                Err(e) => return Err(ExecutionError::StoreError(Box::new(e))),
            };

            // Fire the handler. Per-sub failure is isolated — we ignore the result.
            // Cycles spent before the failure still count toward the sub's gas_remaining.
            let executor = PvmExecutor::new();
            let subscriber_bytes: [u8; 20] = subscriber_addr
                .as_ref()
                .try_into()
                .expect("Address is 20 bytes");
            let _ = executor.execute_handler(
                &mut pvm_ctx,
                &origin.payload,
                &sub.handler_name,
                None,
                None,
                Vec::new(),
                subscriber_bytes,
            );

            (
                pvm_ctx.gas_meters.cycles.used(),
                pvm_ctx.gas_meters.cells.used(),
            )
            // pvm_ctx dropped here, releasing &mut store
        };

        pool_cycles = pool_cycles.saturating_sub(cycles_used);
        pool_cells = pool_cells.saturating_sub(cells_used);

        // Decrement gas_remaining on the sub regardless of handler outcome —
        // the PVM rolls back actor state on raise, but consumed cycles still count.
        sub.gas_remaining = sub.gas_remaining.saturating_sub(cycles_used);
        if let Err(e) = store.set_event_sub(*sub_id, sub).await {
            return Err(ExecutionError::StoreError(Box::new(e)));
        }

        // Bookkeeping event for off-chain indexer audits.
        let mut log_payload = Vec::with_capacity(53);
        log_payload.extend_from_slice(sub_id);
        log_payload.extend_from_slice(origin.emitter.as_ref());
        events.push((origin.emitter, "cip29.async_fire".to_string(), log_payload));
    }

    let cycles_used_total = gas_pool_cycles.saturating_sub(pool_cycles);
    let cells_used_total = gas_pool_cells.saturating_sub(pool_cells);
    Ok((cycles_used_total, cells_used_total, events))
}
```
Diff: return type + local `events` retyped; `cip29.subscription_expired` tagged with `sub.emitter_addr`; `cip29.async_fire` tagged with `origin.emitter`.

---

# execution/src/execution/library_instruction.rs

```rust
// execution/src/execution/library_instruction.rs::execute_publish_library (event-return region at PR head)
pub async fn execute_publish_library<S>(
    store: &mut S,
    sender: &Address,
    name: Vec<u8>,
    code: Vec<u8>,
    block_height: u64,
    gas_meters: &mut DualGasMeters,
) -> Result<Vec<(cowboy_types::Address, String, Vec<u8>)>, ExecutionError>
where
    S: StateStore,
    S::Error: From<cowboy_storage::Error>,
{
    // ... gas charge, validation, content-addressing, storage writes (unchanged) ...
    // ── Events ────────────────────────────────────────────────────────────
    // CIP-26 §3.3: LibraryPublished { publisher, name, code_hash, code_size }
    use crate::execution::library_events::{TOPIC_LIBRARY_PUBLISHED, encode_library_published};
    let event_payload =
        encode_library_published(sender, &name, &code_hash_bytes, code.len() as u64);
    Ok(vec![(
        *sender,
        TOPIC_LIBRARY_PUBLISHED.to_string(),
        event_payload,
    )])
}
```

```rust
// execution/src/execution/library_instruction.rs::execute_remove_library (event-return region at PR head)
pub async fn execute_remove_library<S>(
    store: &mut S,
    sender: &Address,
    name: Vec<u8>,
    gas_meters: &mut DualGasMeters,
) -> Result<Vec<(cowboy_types::Address, String, Vec<u8>)>, ExecutionError>
where
    S: StateStore,
    S::Error: From<cowboy_storage::Error>,
{
    // ... gas charge, validation, existence check, delete (unchanged) ...
    // CIP-26: LibraryRemoved { publisher, name }
    use crate::execution::library_events::{TOPIC_LIBRARY_REMOVED, encode_library_removed};
    let event_payload = encode_library_removed(sender, &name);
    Ok(vec![(
        *sender,
        TOPIC_LIBRARY_REMOVED.to_string(),
        event_payload,
    )])
}
```
Diff: return type retyped; both events tagged with `*sender` (the library publisher). Note: speculative.rs `system_event_emitter` returns `Some(tx_from)` for `Instruction::Library`, re-normalizing to the same publisher.

---

# execution/src/execution/transaction.rs (giant fns — changed regions only)

`execute_transaction` (spans ~47–540) and `execute_deferred_transaction` (spans ~542–1032) are each ~500 lines; full bodies omitted for length. Their changed regions:

```rust
// execution/src/execution/transaction.rs::execute_transaction (signature return-type + system-events map at PR head)
    pub async fn execute_transaction<S: StateStore>(
        &mut self, store: &mut S, tx: &Transaction, block_height: u64,
        block_hash: &Digest, timestamp_ms: u64, pre_verified: bool,
    ) -> Result<
        (u64, u64, ExecutionStatus, Vec<Digest>,
         Vec<(cowboy_types::Address, String, Vec<u8>)>),
        ExecutionError,
    >
    // ... System(sys_inst) arm, after execute_system_instruction(...).await? ...
                // Drain any events emitted by the system instruction (e.g. sys.upgrade.completed)
                // COW-2435: system-instruction events carry a placeholder emitter
                // (the tx sender); `speculative.rs` overrides it with the
                // instruction's canonical system-actor emitter before commitment.
                let mut sys_evts: Vec<(cowboy_types::Address, String, Vec<u8>)> =
                    std::mem::take(&mut self.system_events)
                        .into_iter()
                        .map(|(topic, data)| (tx.from, topic, data))
                        .collect();
                // ... callback_opt path pushes a deferred_tx.created event: ...
                    sys_evts.push((
                        tx.from,
                        "deferred_tx.created".to_string(),
                        event_data.into_bytes(),
                    ));
    // ... after the big instruction match, the destructure was type-annotated: ...
        let (cycles_used, cells_used, status, events): (
            u64, u64, ExecutionStatus,
            Vec<(cowboy_types::Address, String, Vec<u8>)>,
        ) = match execution_result { /* Ok(evts) => ... */ };
```
Note: `self.system_events` is still `Vec<(String, Vec<u8>)>` internally (the PVM/system handlers push 2-tuples); this map wraps each with the placeholder `tx.from`, later corrected by `system_event_emitter`. The `Actor(actor_inst)` and `Library(lib_inst)` arms already return `(Address,String,Vec<u8>)` from their handlers, unchanged here.

```rust
// execution/src/execution/transaction.rs::execute_deferred_transaction (changed regions at PR head)
    async fn execute_deferred_transaction<S: StateStore>(
        &mut self, store: &mut S, tx: &Transaction, origin_tx_hash: &Digest,
        block_height: u64, block_hash: &Digest, timestamp_ms: u64,
    ) -> Result<(u64, u64, ExecutionStatus, Vec<Digest>,
                 Vec<(cowboy_types::Address, String, Vec<u8>)>), ExecutionError>
    // ... System arm: after persisting sender on success ...
                r.map(|_| {
                    // COW-2435: placeholder emitter (tx sender); speculative.rs
                    // overrides it with the canonical system-actor emitter.
                    std::mem::take(&mut self.system_events)
                        .into_iter()
                        .map(|(topic, data)| (tx.from, topic, data))
                        .collect()
                })
    // ... destructure type-annotated identically to execute_transaction ...
    // ... Ok(evts) arm: deferred_tx.executed ...
                let mut all_events = evts;
                all_events.push((
                    tx.from,
                    "deferred_tx.executed".to_string(),
                    event_data.into_bytes(),
                ));
    // ... three Err arms (OutOfCycles / OutOfCells / other) each return: ...
                    vec![(
                        tx.from,
                        "deferred_tx.failed".to_string(),
                        event_data.into_bytes(),
                    )],
```
Diff: return type retyped; drained `system_events` mapped to `(tx.from, …)`; `deferred_tx.executed` and all three `deferred_tx.failed` lifecycle events tagged with `tx.from`.

---

# execution/src/execution/actor_instruction.rs (giant fns — changed regions only)

`execute_actor_instruction` (spans ~398–823) and `execute_actor_handler_impl` (spans ~824–1648) are ~425 and ~824 lines; full bodies omitted for length. Their changed regions:

```rust
// execution/src/execution/actor_instruction.rs::execute_actor_instruction (signature + init_events + deferred_created_events at PR head)
    pub(super) async fn execute_actor_instruction<S: StateStore>(
        &mut self, store: &mut S, tx: &Transaction, inst: &ActorInstruction,
        sender: &Address, _sender_account: &mut Account, gas_meters: &mut DualGasMeters,
        block_height: u64, block_hash: &Digest, timestamp_ms: u64,
        deferred_tx_hashes: &mut Vec<Digest>,
    ) -> Result<Vec<(cowboy_types::Address, String, Vec<u8>)>, ExecutionError>
    // ... Deploy path: init handler events retyped ...
                let init_events: Vec<(cowboy_types::Address, String, Vec<u8>)> = if let Some(
                    handler,
                ) = init_handler.as_deref() { /* self.execute_actor_handler_impl(...) */ };
```

```rust
// execution/src/execution/actor_instruction.rs::execute_actor_handler_impl (signature + deferred_created_events + return at PR head)
    async fn execute_actor_handler_impl<S: StateStore>(
        &mut self, store: &mut S, tx: &Transaction, actor: &Address, handler: &str,
        payload: &[u8], sender: &Address, gas_meters: &mut DualGasMeters,
        block_height: u64, block_hash: &Digest, timestamp_ms: u64,
        deferred_tx_hashes: &mut Vec<Digest>, pinned_libraries: Vec<pvm_runtime::PinnedLibrary>,
    ) -> Result<Vec<(cowboy_types::Address, String, Vec<u8>)>, ExecutionError>
    // ... after extracting side_effects from the PVM host ...
            let deferred_requests = std::mem::take(&mut *deferred_ref.lock().unwrap());
            // COW-2435: (emitter, topic, data) — emitter is the actor that spawned
            // the deferred tx (the actor being executed).
            let mut deferred_created_events: Vec<(Address, String, Vec<u8>)> = Vec::new();
            for req in deferred_requests {
                // ... on success (both the "actor_handler" branch and the CIP-29/msg branch): ...
                    deferred_created_events.push((
                        actor_address_clone,
                        "deferred_tx.created".to_string(),
                        event_data.into_bytes(),
                    ));
            }
    // ... final assembly (unchanged in shape; side_effects.events already carries emitter): ...
            let mut all_events = side_effects.events;   // per-event emitter from emit_event/sync_fire/upgrade
            all_events.extend(deferred_created_events);  // deferred.created tagged actor_address_clone
            Ok(all_events)
```
Diff: both signatures retyped; the two `deferred_tx.created` pushes (worktree lines ~1076 "actor_handler" source and ~1306 "message"/"cip29" source) now include `actor_address_clone` as emitter. `side_effects.events` flows up unchanged in shape (it is `ExecutionSideEffects.events`, already `(Address,String,Vec<u8>)`).

---

# Cross-references — end-to-end emitter attribution trace

The attribution chain, from where the emitter is stamped to where it is committed:

**1. Stamp (per-event true emitter) — pvm_host.rs.** `emit_event` / `fire_sync_subscribers` / `upgrade_self` push `(self.ctx.actor_address, topic, data)`. `ctx.actor_address` is the current call frame's actor; on a nested `call_actor` it is the callee (swapped by `switch_to_callee` / restored by `restore_call_snapshot`). System handlers instead push 2-tuples into `self.system_events`.

**2. Collect — actor_instruction.rs::execute_actor_handler_impl.** `side_effects.events` (from `ExecutionSideEffects.events`, populated via `clone_side_effects_refs` → `ctx.events`) is returned as `all_events`, plus deferred `deferred_tx.created` events tagged `actor_address_clone`.

**3. Placeholder for system/library — transaction.rs.** `execute_transaction` / `execute_deferred_transaction` map `self.system_events` (2-tuples) to `(tx.from, topic, data)` — a PLACEHOLDER emitter — and tag deferred lifecycle events with `tx.from`.

**4. Executor trait boundary — traits.rs / transaction_executor_impl.rs.**
```rust
// storage/src/traits.rs::TransactionExecutor::execute_transactions (return element retyped)
    async fn execute_transactions<S: StateStore + Send>(...)
        -> Result<Vec<(u64, u64, ExecutionStatus, Vec<Digest>,
                       Vec<(cowboy_types::Address, String, Vec<u8>)>)>, ...>;
// execution/src/execution/transaction_executor_impl.rs — the impl mirrors the same retyped return.
```
Called by `execute_block_speculative` (per `storage/src/traits.rs:538` doc-comment and `storage/src/process_block.rs`).

**5. Normalize + commit — speculative.rs::execute_block_speculative.** For each tx, `system_event_emitter(&tx.instruction, tx.from)` decides:
   - `Some(canonical)` (System/Library instr) → overwrite ALL events' emitter with the canonical system actor (UpgradeActor→target `actor`; CBSS ops→`CBSS_SYSTEM_ACTOR`; Token ops→`TOKEN_REGISTRY_SYSTEM_ACTOR`; Library→`tx.from`), discarding the placeholder.
   - `None` (Actor instr) → keep the per-event emitter from step 1 (the true callee).
   Then `compute_logs_root(&events)` and `compute_bloom(&events)` commit the emitter into the receipt; the receipt itself carries `events`.

**6. Persist per-emitter — speculative.rs.** Events are grouped into `BTreeMap<Address, Vec<ActorEvent>>` (deterministic sorted iteration) and each group appended via `append_actor_events(emitter, …)`.
```rust
// storage/src/accounts.rs::append_actor_events (callee — persists to the emitter's log)
    pub async fn append_actor_events(
        &mut self,
        actor: Address,
        new_events: Vec<ActorEvent>,
    ) -> Result<(), Error> {
        if new_events.is_empty() { return Ok(()); }
        if !self.batch_mode {
            return Err(Error::StorageState(
                "must call begin_batch() before append_actor_events()".into(),
            ));
        }
        let mut list = self
            .get_actor_events(&actor)
            .await?
            .unwrap_or_else(|| ActorEventList { events: Vec::new() });
        list.events.extend(new_events);
        if list.events.len() > MAX_ACTOR_EVENTS {
            let drop = list.events.len() - MAX_ACTOR_EVENTS;
            list.events.drain(0..drop);
        }
        let key = StateKey::actor_events(actor);
        let val = Some(StateValue::ActorEventList(list));
        self.state_pending.push((key, val.clone()));
        self.state_pending_map.insert(key, val);
        Ok(())
    }
```
`append_actor_events` was NOT signature-changed by the PR; the `ActorEvent`s it receives now carry `emitter` (each equal to the `actor` key they are appended under). Its per-actor `MAX_ACTOR_EVENTS` trim now runs per-emitter group.

**Consistency anchor:** the emitter that goes into `compute_logs_root`/`compute_bloom`/receipt (step 5) is the SAME normalized `events` value grouped for persistence (step 6) — both use the post-`system_event_emitter` `events` binding, so the committed `logs_root` and the per-actor log agree on emitter.

---

# Truncated / omitted files (no silent caps)

**Truncated to changed-regions-with-context (full bodies too large; execution/ priority):**
- `execution/src/execution/transaction.rs` — `execute_transaction` (~500 lines) and `execute_deferred_transaction` (~490 lines): only signature/type-annotation and event-tagging regions shown; unchanged gas/nonce/fee/basefee/callback logic elided.
- `execution/src/execution/actor_instruction.rs` — `execute_actor_instruction` (~425 lines) and `execute_actor_handler_impl` (~824 lines): only signature/deferred-event/return regions shown; unchanged deploy/PVM-invoke/timer-flush logic elided.
- `execution/src/pvm_host.rs::fire_sync_subscribers` and `::upgrade_self` — only the event-push regions shown; unchanged subscriber-fire / code-swap logic elided.
- `storage/src/speculative.rs::execute_block_speculative` — only the per-tx receipt-build + event-commit loop region shown; unchanged basefee/gas-lane/root-computation surrounding logic elided. The parallel timer/CBSS `ActorEvent`-construction edits (emitter field additions) are described, not quoted.
- `storage/src/types.rs::TransactionReceipt::rlp_encode` — only the log-item region shown; the surrounding RLP field list is unchanged.

**Omitted entirely (non-priority: cli / client / indexer / rpc — all mechanical, no consensus surface):**
- `cli/src/commands.rs` — 5 receipt-event loop destructures `(topic, data)` → `(_emitter, topic, data)`.
- `client/src/rpc.rs` — `TransactionReceiptResponse.events` field `Vec<(String,String)>` → `Vec<(String,String,String)>` + test.
- `indexer/src/db.rs`, `indexer/src/lib.rs` — test `ActorEvent`/receipt constructions add `emitter:` / 3-tuples.
- `indexer/src/json.rs` — `receipt_to_json` emits an `"emitter"` hex field per event; tests updated.
- `rpc/src/handlers/chain.rs` — `ActorEventResponse` gains `emitter`; receipt-events map produces `(emitter_hex, topic, data_hex)`; tests updated.
- `rpc/src/responses.rs` — `TransactionReceiptResponse.events` → 3-tuple; `ActorEventResponse` gains `emitter: String` (+schema doc).
- `rpc/src/rpc.rs` — test 3-tuple update.

**Omitted (priority files, but changes are test-only / trivial field additions — noted, not quoted):**
- `storage/src/{lib,state_invariants,state_value}.rs`, `storage/src/accounts.rs` (tests) — mock `TransactionExecutor` return-type retyping and test `ActorEvent` `emitter:` additions.
- `storage/src/cbss_reshare_overflow.rs` — production `ActorEvent` construction adds `emitter: CBSS_SYSTEM_ACTOR` (consistent with `system_event_emitter`'s CBSS routing).
- `execution/src/execution/tests.rs`, `execution/src/pvm_executor.rs` (tests), `execution/src/pvm_host.rs` (tests) — event-tuple destructure/construction updates.
