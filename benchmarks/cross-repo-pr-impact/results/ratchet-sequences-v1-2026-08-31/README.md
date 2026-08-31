# Escape-ratchet sequence task

Each of the three sequences starts from a strict-E2 escape, registers a permanent check, replays the triggering scope, and adds an unrelated synthetic scheduling control. Passing requires registration, recurrence scheduling, real failure evidence, a blocking decision, and no scheduling on the unrelated control.

The included current-Marshal run is intentionally diagnostic: all three checks enter `InvariantRegistry`, but none is returned by `Orchestrator.plan`, so recurrence scheduling and end-to-end ratchet rates are zero. This is a measured product gap, not a label failure.
