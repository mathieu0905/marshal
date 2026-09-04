# Escape-ratchet sequence task

Each of the three sequences starts from a strict-E2 escape, registers a permanent check, replays the triggering scope, and adds an unrelated synthetic scheduling control. Passing requires registration, recurrence scheduling, real failure evidence, a blocking decision, and no scheduling on the unrelated control.

The included current-Marshal run is intentionally diagnostic. All three checks enter
`InvariantRegistry`, all three are selected again when the recorded source repository
and path scope recurs, and none is selected for the unrelated control. Registration,
recurrence scheduling, and unrelated-change abstention are therefore 1.0.

The released package still does not contain a runnable recurrence workspace for these
three historical checks. `recurrence_execution` and `recurrence_decision` consequently
remain `not_assessed`; failure-evidence, blocking, and end-to-end ratchet rates remain
zero. Scheduling success must not be reported as end-to-end ratchet success.

Execution evidence is evaluator-owned and stored separately in
`evaluator-execution-results.jsonl`. Fields named `recurrence_execution` in system
output are ignored by the scorer; they cannot create failure evidence.
