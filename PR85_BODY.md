Adds an opt-in, single C++ ROS 2 planner that turns timestamped ball observations and registered robot pose into model-validated schema-2 shadow commands. It combines the six-state CKF, deterministic incoming prediction, local contact selection, shared outgoing physics, impact reconstruction and actual runner receiver compatibility. Legacy remains the default.

Conflict resolution is complete against `hitchopen/HOPE:nightly_built` at `91aecabfd44cb258ac998158e724be9017d883a7`. Ordinary merge `e7947b9` resolved 18 conflicts (12 content, 6 add/add), retaining current upstream deployment, runtime-plane/session-home behavior, dependencies and receiver semantics. The final scope manifest accounts for all 175 changed paths.

**Planner software qualification remains open.** The clean exact-source run failed `base_yaw_chain_150_0`: 39/43 eligible updates (90.6977%, required ≥95%). Its raw aggregate exit remains 1. The missing epochs are retained and their first lost production stage is unresolved; source pacing alone does not establish causation.

Corrections include bounded stage-loss accounting, aligned source state/stamps, bounded depth-eight integrated ingress, actual consumed-prefix parity, context-safe relay/planner shutdown, a single V2 executor and a measured 5 ms publication reserve. The 95% coverage, 30 ms publication-completion and decoder P95 thresholds are unchanged.

Tested source: `dc012fe970d6bb2169853dd8e985705193ac9148`. Submitted head: `4d2247c69100f1e5416a8f42468b4d67418c45fb` (four documentation receipts only). Any later submitted commit changes only qualification/integration receipts; [final-delivery.json](https://github.com/timothyypark/HOPE/blob/evidence/pr85-software-qualification-20261024/final-delivery.json) records the exact submitted head and hash equivalence.

| Verification | Result |
|---|---|
| Native C++ / ASan+UBSan | 20/20 groups each |
| ROS messages / planner / bringup | 2/2; 106/107; 25/27 |
| Inherited lint | flake8 and pep257; no added normalized findings |
| Historical/current-upstream legacy parity | 701 cases each |
| V2 cutoff parity / DOP853 outgoing reference | 789 / 144 cases |
| Accounting-on/off diagnostics | 8/8 |
| Five repetitions × 32 nominal profiles | 157/160 pass; 3 fail |

The verifier skipped the repeated campaign after the ROS audit failed. The entire predeclared campaign was then completed separately on unchanged source and binaries; it is not presented as a coherent passing invocation. Historical failed runs, all per-trial denominators, exceptions, stage/receiver ledgers and resource receipts remain available.

- [Integration receipt and conflict ledger](https://github.com/timothyypark/HOPE/blob/4d2247c69100f1e5416a8f42468b4d67418c45fb/hope_ws/src/hope_planner_cpp/docs/integrated_planner_pr85_integration.md).
- [Scoped result, M01–M08 / CL01–CL20 checklist and every trial](https://github.com/timothyypark/HOPE/blob/evidence/pr85-software-qualification-20261024/integrated_planner_software_qualification.md).
- [Downloadable evidence and checksum verification](https://github.com/timothyypark/HOPE/tree/evidence/pr85-software-qualification-20261024).

Output remains shadow-only. Planner software qualification, simulation qualification, physical qualification and deployment authorization remain false. This PR requests review of the planner-to-command contribution; it does not authorize robot actuation or claim demonstrated physical return performance. No upstream merge or PR draft-state change was performed.

Failed repeated trials:

- Repetition 1, `review_chain_300_12_unknown`: 37/40; AssertionError: ('command coverage', 37, 40, 0.925).
- Repetition 4, `review_chain_150_12_zero`: 18/20; AssertionError: ('command coverage', 18, 20, 0.9).
- Repetition 5, `review_refresh_300_10_unknown`: 149/160; AssertionError: ('command coverage', 149, 160, 0.93125).
