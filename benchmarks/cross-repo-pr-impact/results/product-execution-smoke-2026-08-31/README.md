# Product execution smoke run

The frozen ranker placed `wandertracks/wandertracks-android` at rank 2. After predictions were frozen, the evaluator ran the dataset-fixed parity command on fresh A0/A1/A2 worktrees. All arms ran five checks and returned 0/1/0.

The product scorer keeps the complete 50-target denominator: one target has evaluator-owned execution evidence and 49 remain `not_assessed`. Consequently strict causal execution accuracy and evidence-card completeness are both 0.02, while `not_assessed` is 0.98. The run demonstrates the execution interface without presenting one replay as a completed 50-case product evaluation.
