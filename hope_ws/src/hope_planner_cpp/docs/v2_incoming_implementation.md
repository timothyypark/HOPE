# V2 incoming prediction drop-in: implementation and verification record

Status: implementation in progress; no software qualification or deployment authorization.

The approved October 28 plan starts at PR85 `4d2247c69100f1e5416a8f42468b4d67418c45fb`
and upstream nightly `91aecabfd44cb258ac998158e724be9017d883a7`. Both remote heads
were fetched and verified unchanged before creating
`feature/v2-incoming-validity-continuous-dropin`. PR85 history is preserved.
The existing PR85 tested executable source is `dc012fe970d6bb2169853dd8e985705193ac9148`;
its submitted descendant changes only documentation. Baseline receipts are under
`/workspace/.cloud-setup/v2-incoming/baseline` until portable publication.

## Required boundaries

- One authoritative V2 physical state and event history, with immutable causal
  snapshots for the packet-triggered command and continuous forecast consumers.
- The current HOME/RuntimePlaneReference selector owns the executable plane.
  Precommit per-ball previews are tentative and cannot authorize a command.
- Existing RacketTargetPlanner and schema-4/5 semantics remain authoritative.
  The integrated prototype's outgoing solver is not the drop-in solver.
- Physical state availability, strike support, command eligibility, and Runner
  commitment are distinct. Revocation must survive delayed results and delivery.
- Actual Runner pre-engagement revocation is a verification gate; after-engagement
  cancellation and active mid-swing updates remain outside this contribution.
- Legacy remains the default; new outputs stay protected and shadow-only.

## Ordered work and evidence

| Step | Required result | State |
|---|---|---|
| Baseline | Source/config hashes, native/ROS/receiver/plane/parity receipts, retained failures | In progress |
| Bounce | Isolated outlier rejected as contact; genuine/double/sparse/restored contacts tested | Native checks pass |
| Adapter | Explicit validity result and V2-to-StrikeTarget downstream parity | Native checks pass |
| Coordinator | One owner, bounded history, packet prefix reconciliation and revocation epochs | Pending |
| Plane and managed backend | Existing plane and one-shot planner integration, actual schema 4/5 | Pending |
| Runner | Before-publication, before-engagement and engaged lifecycle evidence | Pending |
| Continuous | Independent forecasts and statuses through commitment and recovery | Pending |
| Qualification | IV01–IV24, gates A–L, native/sanitizer/ROS/rate/parity/accuracy evidence | Pending |

User clarification makes closure of all four existing PR85 coverage failures
mandatory: `base_yaw_chain_150_0`, `review_chain_300_12_unknown`,
`review_chain_150_12_zero`, and `review_refresh_300_10_unknown`.
Passing diagnostic repetitions cannot erase the historical failures.

Existing source-epoch qualification retains its >=95% coverage, <=30 ms
publication-completion age and <=30 ms per-run decoder P95 limits. Before scoring
the new architecture, separately freeze continuous forecast opportunities and
one-shot committed-flight opportunities, including all exclusions and counters.
Do not use a lower-rate full-trajectory publisher to redefine source coverage.
Run finite timing campaigns without concurrent compilation or archival work.

Keep commits limited to coherent changes with focused checks; run the complete
clean ladder and predeclared repetitions on the final exact source. Preserve
failures, raw evidence, binary/config hashes and limits on physical accuracy.

## Contact correction receipt

The new isolated-outlier and restored-outlier regressions fail on the pinned
source and pass after independent post-contact motion corroboration was added.
A separate analytic impact with deliberately mismatched filter restitution
remains detected despite rejected post-contact observations at 150/300/360 Hz.
All 21 native groups pass, including inherited close double-bounce, sparse,
fast overlapping-window, restored contact and selected upstream receiver tests.
Logs: `v2-incoming/baseline/contact-before.{log,xml,exit}` and
`v2-incoming/contact-tests.{log,exit}` under the environment evidence root.
Sanitizer and ROS qualification remain pending.

## Adapter receipt

Explicit availability/support/eligibility statuses, committed/tentative managed
plane conversion, source-prefix identity and terminal-evidence checks are native
interfaces. Adapter checks cover 27 position/speed/plane-mode combinations with
exact outgoing vector and serialized-packet equality, followed by the actual
schema-4/5 receiver. Existing RuntimePlaneReference tests also pass. These are
component checks; the ROS drop-in and Runner engagement gate are still pending.
