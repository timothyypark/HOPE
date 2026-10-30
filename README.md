# HOPE V2 simulation verification evidence

Qualified source: [`96034645f26b1597c093281a398fa0e62d5c93b5`](https://github.com/timothyypark/HOPE/tree/96034645f26b1597c093281a398fa0e62d5c93b5).

Code and review: [draft PR #1](https://github.com/timothyypark/HOPE/pull/1), branch `feature/v2-incoming-validity-continuous-dropin`.

Read [the assessment](ASSESSMENT.md) for results, limits and unresolved coverage defects. The report distinguishes original raw verdicts from current per-flight findings. No hardware deployment or physical accuracy is claimed.

## Inspect the results

- [Current verification summary](reports/verification-summary.json)
- [Every failure disposition](reports/failure-dispositions.json)
- [Historical lifecycle replay](reports/historical-lifecycle-replay.json)
- [Tracing enabled/disabled comparison](reports/lifecycle-instrumentation-comparison.json)
- [Actual Runner comparison](reports/runner-revocation.json) and [recorded-command replay](reports/runner-recorded-assessment.json)
- [Full campaign flight accounting](reports/campaign-outcome-assessment.json)
- [Historical failure accounting](reports/historical-audit-reproducible.json)
- [Actual decoder retention and revocation](reports/decoder-lifetime-assessment.json)
- [Contact conversion simulation](reports/incoming-conversion-result.json)
- [Supplied MuJoCo outgoing-flight replay](reports/mujoco-conversion-result.json)
- [Packet-prefix diagnosis](reports/packet-prefix-failures.json)
- [Source/build declaration](reports/qualification-declaration.json)
- [Actual forecast and ground-truth plots](plots/)
- [Archive checksums](archives.json) and [per-file SHA-256 inventory](inventory.jsonl)

The plots compare independent ball truth with actual V2 waypoints and show the contact plane, target and racket normal. MuJoCo starts the outgoing ball at that contact with the reconstructed legacy-impact velocity; the robot is pinned. This does not simulate a policy-driven racket collision.

## Restore raw receipts

Each archive beneath `receipts/` contains paths relative to the original evidence root. Extract selected archives into one empty directory to recreate the relevant tree:

```sh
mkdir restored
tar -xzf receipts/qualification-01/gates.tar.gz -C restored
```

Campaign archives are grouped by repetition and profile. They retain raw JSON, source records, decoder records, stage traces, process logs and original exit codes. Their original absolute workspace paths remain provenance, not required installation locations. `inventory.jsonl` hashes the uncompressed members; packaging also independently decompressed and verified every member. Build products and installed dependencies are omitted; pinned source, build commands, test output and binary hashes identify the tested artifacts.

Historical receipts remain on the separate unchanged [2026-10-29 evidence branch](https://github.com/timothyypark/HOPE/tree/evidence/v2-incoming-qualification-20261029). Paths beginning `/workspace/.cloud-setup/v2-incoming/` refer to that earlier evidence root. Paths beginning `/workspace/.cloud-setup/v2-simulation-verification/` refer to this branch's restored tree.

The standalone diagnostic replay and packaging scripts are retained in `receipts/setup-and-analysis.tar.gz`. They supplement the committed production-component probes and verification scripts; they do not alter the tested runtime.
