# PPQ004 fresh recovery campaign — November 14, 2026

This branch preserves fresh validation evidence for the reconstructed
[implementation](https://github.com/timothyypark/HOPE/tree/feature/ppq004-recorded-validation).
The previous local November 12 campaign receipts were not recoverable in the
restored workspace. New runs are not represented as those original receipts.

Status: environment rebuilt; full campaign running against committed source
`f4902023d49c85ff57da62a618b2001181d3b8e7`. Completed component receipts are in
[recovery-progress](recovery-progress): archive integrity, benchmark reproduction,
native and sanitizer suites, conversion checks and historical parity. These are
partial results, not a passing whole-system qualification. Hardware is
protocol-only and will remain NOT_RUN. Completed evidence is pushed in stages.

The published source at `55799d4` retained the recordings, archive hashes,
reviewed annotations, frozen targets, state/trajectory tests and campaign tools.
The missing orientation/duplicate fixtures, delayed-command exposure and spin
fault-reporting checks have been reconstructed in new commits. Original October
historical-loss inputs were recovered from the published evidence branches; their
provenance is retained in the recovery-progress manifest. November 12 raw outputs
remain unavailable.
