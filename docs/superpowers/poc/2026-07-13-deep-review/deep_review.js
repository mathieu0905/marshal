export const meta = {
  name: 'deep-review-poc',
  description: 'Deep review PoC: closure -> scout hypotheses -> dedup/cap -> prove (trigger-or-refute)',
  phases: [
    { title: 'Scout', detail: 'per-lens failure-hypothesis enumeration over the change closure' },
    { title: 'Prove', detail: 'one high-effort agent per hypothesis: construct a concrete trigger or refute' },
  ],
}

// ---- args (all optional; defaults tuned for a cheap calibration run) ----
// { closure, diff, baseLenses:[{name,prompt}], ratchetLenses:[{name,prompt}],
//   lensSubset?:[names], maxHypPerLens=6, globalHypCap=30, proveEffort='high' }
const A = (typeof args !== 'undefined' && args && Object.keys(args).length)
  ? args : (typeof EMBED !== 'undefined' ? EMBED : {})
const CLOSURE = A.closure || ''
const DIFF = A.diff || ''
const maxHypPerLens = A.maxHypPerLens ?? 6
const globalHypCap = A.globalHypCap ?? 30
const proveEffort = A.proveEffort || 'high'

let lenses = [...(A.baseLenses || []), ...(A.ratchetLenses || [])]
if (A.lensSubset && A.lensSubset.length) {
  const keep = new Set(A.lensSubset)
  lenses = lenses.filter(l => keep.has(l.name))
}

// L1: one identical SHARED prefix reused verbatim in every agent prompt so the
// API prompt-cache hits after the first agent (the closure+diff is the bulk of tokens).
const SHARED =
  `# CHANGE CLOSURE (enclosing functions at PR head; shared context)\n${CLOSURE}\n\n` +
  `# UNIFIED DIFF (PR#936)\n\`\`\`diff\n${DIFF}\n\`\`\`\n`

const HYP_SCHEMA = {
  type: 'object',
  properties: {
    hypotheses: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          title: { type: 'string' },
          claim: { type: 'string', description: 'if <state/input> then <which invariant breaks>' },
          where: { type: 'string', description: 'file::fn or file:line' },
          invariant_broken: { type: 'string' },
          priority: { type: 'integer', description: '1=low .. 5=must-check' },
        },
        required: ['title', 'claim', 'where', 'priority'],
      },
    },
  },
  required: ['hypotheses'],
}

const PROVE_SCHEMA = {
  type: 'object',
  properties: {
    verdict: { type: 'string', enum: ['confirmed', 'refuted', 'uncertain'] },
    trigger: { type: 'string', description: 'concrete inputs/state -> wrong output/halt/fork; empty if refuted' },
    severity: { type: 'string', enum: ['low', 'mid', 'high'] },
    dimension: { type: 'string' },
    reason: { type: 'string' },
  },
  required: ['verdict', 'severity', 'reason'],
}

const spent0 = budget.spent()

// ---- Scout: enumerate hypotheses per lens (medium effort, wide & cheap) ----
phase('Scout')
const scoutResults = await parallel(lenses.map(lens => () =>
  agent(
    `${SHARED}\n---\n# REVIEW LENS: ${lens.name}\n${lens.prompt}\n\n` +
    `Enumerate AT LEAST ${maxHypPerLens} distinct FAILURE HYPOTHESES about this change ` +
    `through the lens above. Include "boring" ones. Do NOT verify or rank down — just ` +
    `surface concrete, checkable ways this change could be wrong. For each: a crisp title, ` +
    `an "if <state/input> then <invariant breaks>" claim, the file::fn location, the ` +
    `invariant at risk, and a priority 1-5.`,
    { label: `scout:${lens.name}`, phase: 'Scout', schema: HYP_SCHEMA, effort: 'medium' }
  ).then(r => ({ lens: lens.name, hyps: (r && r.hypotheses) || [] }))
))

// ---- L2: dedup + cap. Per-lens cap, then global cap by priority. ----
function normKey(h) {
  const w = (h.where || '').toLowerCase().replace(/:\d+$/, '')
  const t = (h.title || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim().slice(0, 40)
  return `${w}|${t}`
}
const seen = new Set()
let pooled = []
for (const sr of scoutResults.filter(Boolean)) {
  const capped = [...sr.hyps].sort((a, b) => (b.priority || 0) - (a.priority || 0)).slice(0, maxHypPerLens)
  for (const h of capped) {
    const k = normKey(h)
    if (seen.has(k)) continue
    seen.add(k)
    pooled.push({ ...h, lens: sr.lens, key: k })
  }
}
pooled.sort((a, b) => (b.priority || 0) - (a.priority || 0))
const rawCount = pooled.length
if (pooled.length > globalHypCap) {
  log(`L2 cap: ${pooled.length} unique hypotheses -> keeping top ${globalHypCap} by priority (${pooled.length - globalHypCap} dropped)`)
  pooled = pooled.slice(0, globalHypCap)
}
log(`Scout done: ${scoutResults.filter(Boolean).length} lenses -> ${rawCount} unique hypotheses -> ${pooled.length} to prove`)

// ---- Prove: one high-effort agent per hypothesis; trigger-or-refute ----
phase('Prove')
const proven = await parallel(pooled.map(h => () =>
  agent(
    `${SHARED}\n---\n# PROVE-OR-REFUTE\nHypothesis (from lens ${h.lens}): ${h.title}\n` +
    `Claim: ${h.claim}\nLocation: ${h.where}\nInvariant at risk: ${h.invariant_broken || '(unstated)'}\n\n` +
    `Trace the ACTUAL code path in the closure. You must either (a) CONFIRM by giving a ` +
    `CONCRETE trigger — specific inputs/state that drive the path to a wrong output, halt, ` +
    `or consensus fork — or (b) REFUTE with the guard/precondition/design fact that makes it ` +
    `impossible. If you can't get to a trigger but can't rule it out, say "uncertain". ` +
    `A demonstrated trigger outranks any opinion. Do not confirm without a trigger.`,
    { label: `prove:${h.lens}:${(h.where || '').slice(0, 24)}`, phase: 'Prove', schema: PROVE_SCHEMA, effort: proveEffort }
  ).then(v => v ? { ...h, ...v } : null)
))

const findings = proven.filter(Boolean)
const confirmed = findings.filter(f => f.verdict === 'confirmed')
const uncertain = findings.filter(f => f.verdict === 'uncertain')
const spent = budget.spent() - spent0

log(`Prove done: ${confirmed.length} confirmed, ${uncertain.length} uncertain, ${findings.filter(f => f.verdict === 'refuted').length} refuted`)

return {
  mode: 'deep',
  lenses: lenses.map(l => l.name),
  scout: { unique_hypotheses: rawCount, proved: pooled.length },
  confirmed: confirmed.map(f => ({ title: f.title, where: f.where, dimension: f.dimension, severity: f.severity, lens: f.lens, trigger: f.trigger, reason: f.reason })),
  uncertain: uncertain.map(f => ({ title: f.title, where: f.where, severity: f.severity, lens: f.lens, reason: f.reason })),
  tokens_spent: spent,
}
