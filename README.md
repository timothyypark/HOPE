# PR85 integration and software verification evidence

**Integration passed. Planner software qualification failed.**

Tested source: [`dc012fe970d6bb2169853dd8e985705193ac9148`](https://github.com/timothyypark/HOPE/commit/dc012fe970d6bb2169853dd8e985705193ac9148). Upstream target: `91aecabfd44cb258ac998158e724be9017d883a7`. Existing PR: [hitchopen/HOPE#85](https://github.com/hitchopen/HOPE/pull/85).

The clean full run failed `base_yaw_chain_150_0` at 39/43 eligible command epochs (90.6977%, required ≥95%). Its aggregate exit remains 1. Two inherited bringup lint categories also remain failing, with no new findings.

The separately continued, predeclared campaign completed **157/160 passing trials and 3 failing trials** on unchanged source, contract and binaries. All outcomes are retained; no retries were credited. The campaign cannot turn the earlier failed full invocation into a pass.

## Start here

- [Scoped qualification receipt and all trial results](integrated_planner_software_qualification.md).
- [Machine-readable receipt](integrated_planner_software_qualification.json), [campaign summary](campaign-summary.json), [frozen contract](qualification-contract.json).
- [Final base-yaw failure analysis](final-base-yaw-failure-analysis.json). Actual-stage attribution remains unresolved for that uninstrumented run.
- [Repeated-campaign failure analysis](final-campaign-failure-analysis.json), [tested binary and runtime-library hashes](final-binary-inventory.json), and [policy Python dependencies](policy-python-dependencies.json).
- [Integration receipt and all 18 conflict resolutions](https://github.com/timothyypark/HOPE/blob/dc012fe970d6bb2169853dd8e985705193ac9148/hope_ws/src/hope_planner_cpp/docs/integrated_planner_pr85_integration.md); original index/stage blobs are in the integration archive.
- [Final delivery proof](final-delivery.json): submitted head, tested-source equivalence, remote evidence commit, live GitHub mergeability/checks and PR-description write result.
- [Prepared PR85 description](PR85_BODY.md), provided for manual application if the GitHub credential still cannot update the upstream PR.

## Verification performed

- Native C++ 20/20 and ASan/UBSan 20/20 groups passed.
- All 136 registered ROS groups ran: messages 2/2, planner 106/107, bringup 25/27. One new planner coverage failure and two inherited lint categories are explicit.
- Two 701-case legacy comparisons, 789 V2 cutoffs and 144 independent outgoing numerical cases passed.
- Eight accounting-on/off trials passed. The 32 × 5 campaign ran separately after the full verifier skipped it on the failed ROS prerequisite.
- Actual receiver decoding, identity/restart behavior, policy observation construction, fault/expiry/reacquisition, spin/base semantics and failure-safe receipts were exercised.

## Download and verify

Use a new directory. This evidence branch has an independent Git history and does not add binary archives to the PR diff.

```bash
git clone --single-branch --branch evidence/pr85-software-qualification-20261024 https://github.com/timothyypark/HOPE.git hope-pr85-evidence
cd hope-pr85-evidence
python3 verify_artifacts.py artifacts --output local-verification.json
```

`verify_artifacts.py` uses Python standard-library modules. It verifies each part, the reconstructed archive bytes and every manifested raw member, and performs a limited credential-pattern scan. Compare its result with the published `artifact-verification.json`.

Archives exceeding 24 MiB are split into ordered 20 MiB parts. To extract one split archive after verification, concatenate its `.part000`, `.part001`, … files in order and pipe to `tar -xz -C <empty-directory>`. Unsplit archives can be extracted with `tar -xzf`. Paths inside archives are relative to `.cloud-setup/`; they preserve the original `pr85-integration/` and `pr85-qualification/` layout.

| Archive | Contents |
|---|---|
| environment-support | Offline ROS XML schema catalog and schemas |
| integration-checkpoint | Pins, conflict index/stage blobs/ledger, upstream and merged tests, parity and deployment regression receipts |
| diagnosis-and-failures | All available earlier failed/pilot/cancelled runs, diagnostics, before/after regressions, scripts, dependencies and resource samples |
| final-complete-ladder | Exact-source full invocation, per-gate exits, all ROS/native/sanitizer logs and final failure |
| campaign-freeze-and-summary | Predeclared matrix, source/config/test/binary hashes, commands and all 160 outcomes |
| campaign-repetition-1 … 5 | Every trial raw source/command/actual-decoder stream, summary, accounting, resources, log and exit |
| reacquisition-spin-evidence | Original historical archive, preserved byte-for-byte |

The historical archive is 15,579,488 bytes with SHA-256 `fb23fd72ccdff4bb38e5c9820937ad1ee22421f53c15421cbeecb067c42ea3c8`. Compiled executables and installed dependencies are not part of these portable archives; their hashes and exact build commands are recorded. Old compiler objects/static build archives were reclaimed with inventories. Selected old sanitizer binaries were losslessly retained locally in separate archives; those binary archives are not published here.

## Reproduce the tested source

Check out `dc012fe970d6bb2169853dd8e985705193ac9148` in a separate source clone. Use ROS Jazzy on Ubuntu 24.04 with the dependency versions recorded in `diagnosis-and-failures`, Fast DDS on localhost and the recorded parent CPU/memory limits. Source the ROS environment and run the repository verification entry point with a new absolute evidence directory. The selected-upstream build is required for the lint comparison; the archive contains its exact build commands and the final wrapper environment.

The recorded cloud paths identify original execution locations, not a promise of identical paths on another host. Rebuild binaries for the new host; a new timing run is a new empirical result and cannot replace a recorded failure. There is no cross-host or hard-real-time qualification.

Simulation qualification, physical qualification and deployment authorization are false. No live actuation or upstream merge was performed.
