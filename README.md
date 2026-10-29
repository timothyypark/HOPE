# V2 incoming drop-in: implementation and verification evidence

**Software qualification FAIL. Implementation is shadow-only and is not ready for live adoption.**
The complete frozen invocation passed native 25/25, sanitizer 25/25 and Runner
24/24 groups/cases. ROS ran all 159 groups; two planner profiles failed, alongside
two inherited bringup lint gates. The old/new campaigns passed **152/160** and
**83/90** trials. The required original `review_chain_300_12_unknown` failure
remains open. All failed/interrupted runs are preserved.

The later fixture-only commit `f015e0e` leaves tested runtime sources unchanged;
its separate consumer checks passed **13/14**, with no replacement qualification
credit. See the report for the exact failed assertion and its stage diagnosis.

Tested source: [`369dd6cf6bfbf12ce2f4cd87223570fd7ee008df`](https://github.com/timothyypark/HOPE/commit/369dd6cf6bfbf12ce2f4cd87223570fd7ee008df).
Source branch: [`feature/v2-incoming-validity-continuous-dropin`](https://github.com/timothyypark/HOPE/tree/feature/v2-incoming-validity-continuous-dropin).
The baseline is PR85 `4d2247c69100f1e5416a8f42468b4d67418c45fb` against upstream
`91aecabfd44cb258ac998158e724be9017d883a7`. PR85 is unchanged and unmerged.

## Start here

- [Architecture, interface, validity, Runner and qualification report](v2_incoming_implementation.md).
- [Acceptance gates A–L and original four coverage profiles](acceptance-receipt.json).
- [Final complete verification summary](qualification-06-summary.json).
- [All-trial performance, including failures](qualification-06-complete-performance.json).
- [Every failed old-campaign trial](qualification-06-campaign-failure-analysis.json).
- [Post-campaign fixture proof](post-campaign-fixture-proof.json), [observer failure diagnosis](acquisition-observer-failure-analysis.json).
- [Previous complete failed invocation](qualification-05-summary.json).
- [Protected-source audit](scope-audit-final.json), [tested binaries and libraries](final-binary-inventory.json).
- [Archive verification](artifact-verification.json), [lossless raw retention inventory](raw-retention-inventory.json).
- Historical PR85 failures remain published on the separate [PR85 evidence branch](https://github.com/timothyypark/HOPE/tree/evidence/pr85-software-qualification-20261024).

## Download and verify

This branch has an independent Git history. Archives do not enter the implementation diff.

```bash
git clone --single-branch --branch evidence/v2-incoming-qualification-20261029 https://github.com/timothyypark/HOPE.git hope-v2-incoming-evidence
cd hope-v2-incoming-evidence
python3 verify_artifacts.py artifacts --output local-verification.json
```

The standard-library verifier checks every part, reconstructed archive and
manifested member. It also decompresses retained raw gzip members and verifies
their original byte counts and SHA-256 against the retention inventory. Its
credential-pattern scan is limited and is not an exhaustive secret audit.

Archives larger than 24 MiB use ordered 20 MiB parts. After verification, combine
`.part000`, `.part001`, … in order and pipe to `tar -xz -C <empty-directory>`.
Unsplit archives use `tar -xzf`. Paths are relative to the original `.cloud-setup`
evidence directory. Restore an individually compressed raw receipt with
`gzip -dk file.json.gz` (or the corresponding `.stages.gz`/`.tsv.gz` file).

| Archive group | Contents |
|---|---|
| development-and-baseline | Baseline failures, focused regressions, diagnostic comparisons, failed/attempted probes, scripts and environment receipts |
| qualification-01…05-retained | Earlier complete or explicitly interrupted invocations; all available failed outcomes and original exits |
| final-complete-ladder | Final native/sanitizer/ROS/numerical/parity/Runner invocation and original exits |
| repeated-campaign-freeze and repetitions | Original 160-run matrix, source/config/binary hashes, every trial and actual stage trace |
| incoming-campaign-freeze and repetitions | New 90-run/900-flight matrix, every source epoch, candidate/command/decoder stream and synthetic accuracy receipt |
| retained-binary-inventories | Original raw/binary/object hashes and verified lossless-retention mappings; compiled binaries are not shipped |

Installed dependencies, build objects and binaries are excluded from the portable
archives. Their versions, exact commands and hashes are recorded. Real hardware,
HAL transport, the deployed policy identity and held-out physical ball accuracy
remain unverified. The Runner option defaults off and does not cancel an already
engaged swing. Nothing in these receipts authorizes live deployment.
