export const meta = {
  name: 'regular-review-baseline',
  description: 'Baseline mirroring current regular mode: one single-pass agent per base lens, diff-only',
  phases: [
    { title: 'Review', detail: 'one-shot structured findings per base lens over the diff (no closure, no scout/prove)' },
  ],
}

// { diff, baseLenses:[{name,prompt}], lensSubset?:[names], effort='medium' }
const A = (typeof args !== 'undefined' && args && Object.keys(args).length)
  ? args : (typeof EMBED !== 'undefined' ? EMBED : {})
const DIFF = A.diff || ''
const effort = A.effort || 'medium'

let lenses = [...(A.baseLenses || [])]
if (A.lensSubset && A.lensSubset.length) {
  const keep = new Set(A.lensSubset)
  lenses = lenses.filter(l => keep.has(l.name))
}

// Regular mode is diff-scoped and single-pass — deliberately NO change closure.
const SHARED = `# UNIFIED DIFF (PR#936)\n\`\`\`diff\n${DIFF}\n\`\`\`\n`

const FIND_SCHEMA = {
  type: 'object',
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          title: { type: 'string' },
          file: { type: 'string' },
          line: { type: 'integer' },
          dimension: { type: 'string' },
          severity: { type: 'string', enum: ['low', 'mid', 'high'] },
          reason: { type: 'string' },
        },
        required: ['title', 'file', 'severity'],
      },
    },
  },
  required: ['findings'],
}

const spent0 = budget.spent()

phase('Review')
const results = await parallel(lenses.map(lens => () =>
  agent(
    `${SHARED}\n---\n# REVIEW LENS: ${lens.name}\n${lens.prompt}\n\n` +
    `Adversarially review this diff through the lens above — assume it is wrong until proven ` +
    `otherwise. Return structured findings: for each, a title, file, line (if known), the ` +
    `dimension, a severity (low|mid|high), and a one-line reason. Report only real issues.`,
    { label: `review:${lens.name}`, phase: 'Review', schema: FIND_SCHEMA, effort }
  ).then(r => ({ lens: lens.name, findings: (r && r.findings) || [] }))
))

const all = results.filter(Boolean).flatMap(r =>
  r.findings.map(f => ({ ...f, source: r.lens, dimension: f.dimension || r.lens })))
const spent = budget.spent() - spent0

log(`Regular review done: ${lenses.length} lenses -> ${all.length} raw findings`)

return {
  mode: 'regular',
  lenses: lenses.map(l => l.name),
  findings: all.map(f => ({ title: f.title, file: f.file, line: f.line || null, dimension: f.dimension, severity: f.severity, source: f.source, reason: f.reason })),
  tokens_spent: spent,
}
