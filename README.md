# PPQ004 main-versus-CKF accuracy comparison — November 14, 2026

Start with the completed [accuracy comparison report](comparison/REPORT.md),
[graphs](comparison/plots/accuracy-and-coverage.png), and
[reproduction instructions](comparison/REPRODUCE.md).

The recordings do not demonstrate an overall managed-CKF accuracy advantage.
The paired 100 ms estimated-state forecast comparison favors current upstream
main; managed CKF availability is lower. Native receiving-plane accuracy has
only one paired holdout arc and remains inconclusive. No planner runtime was
changed. All code and evidence are published to `timothyypark/HOPE`.

The `recovery-progress/` directory below is inherited evidence from the separate
earlier recovery campaign. That campaign was interrupted and is incomplete;
the new standalone comparison does not close its remaining integration gates.

## Earlier recovery campaign

This branch preserves fresh validation evidence for the reconstructed
[implementation](https://github.com/timothyypark/HOPE/tree/feature/ppq004-recorded-validation).
The previous local November 12 campaign receipts were not recoverable in the
restored workspace. New runs are not represented as those original receipts.

Earlier status: environment rebuilt; campaign started against committed source
`f4902023d49c85ff57da62a618b2001181d3b8e7`. Completed component receipts are in
[recovery-progress](recovery-progress): archive integrity, benchmark reproduction,
native and sanitizer suites, conversion checks and historical parity. These are
partial results, not a passing whole-system qualification. Hardware is
protocol-only and remain NOT_RUN. The earlier full campaign was interrupted;
only the completed receipts retained here are claimed.

The published source at `55799d4` retained the recordings, archive hashes,
reviewed annotations, frozen targets, state/trajectory tests and campaign tools.
The missing orientation/duplicate fixtures, delayed-command exposure and spin
fault-reporting checks have been reconstructed in new commits. Original October
historical-loss inputs were recovered from the published evidence branches; their
provenance is retained in the recovery-progress manifest. November 12 raw outputs
remain unavailable.
