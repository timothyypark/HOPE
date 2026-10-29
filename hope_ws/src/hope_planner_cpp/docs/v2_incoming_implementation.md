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
| Baseline | Source/config hashes, native/ROS/receiver/plane/parity receipts, retained failures | Recorded |
| Bounce | Isolated outlier rejected as contact; genuine/double/sparse/restored contacts tested | Native checks pass |
| Adapter | Explicit validity result and V2-to-StrikeTarget downstream parity | Native checks pass |
| Coordinator | One owner, bounded history, packet prefix reconciliation and revocation epochs | Native component checks pass |
| Plane and managed backend | Existing plane and one-shot planner integration, actual schema 4/5 | Development ROS checks pass |
| Runner | Before-publication, before-engagement and engaged lifecycle evidence | Opt-in veto implemented; qualification pending |
| Continuous | Independent forecasts and statuses through commitment and recovery | Development ROS/rate checks pass |
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

## Coordinator component receipt

Packet samples are reconciled against the actual qualified observation history;
packet epochs are never equated to V2 generations. Bounded checkpoints recover
the exact source cutoff, including filter-rejected observations. Native checks
prove cutoff state/covariance equality, one-shot deduplication, healthy updates,
source faults, expiry, bounded storage and an observed second-bounce race that
retires a pending supported result before its source/contact deadlines expire.
An accepted command retains its original timestamp and absolute contact deadline;
new observations can support that flight without rewriting its source timestamp.
A missing fresh authoritative stream revokes it. ROS integration is pending.

## Managed ROS integration receipt

The opt-in `prediction_backend=v2_incoming` uses the existing solver thread,
packet commitment, RuntimePlaneReference, RacketTargetPlanner and schema-4/5
packer. A bounded packet/observation join waits for the same qualified source
prefix; mismatched histories abstain. One waiting packet takes priority over a
replaceable continuous preview. Dynamic previews remain tentative until the
existing selector runs at packet commitment. Continuous forecasts then retain
that selected plane even when the base moves.

All command/status outputs use the protected `/hope/shadow/v2_incoming/`
namespace. Legacy remains the default. `StrikeCandidateV1` is a companion to
the unchanged `FlightPredictionV2`; its revocation stream retains 64 statuses
separately from latest candidate traffic. Consumers must order by session,
physical generation, HOME epoch and revision. Runner commitment is `UNKNOWN`.

Development checks: six ROS cases cover fixed/per-ball/stable-per-ball valid
commands, actual receiver decoding, frozen planes, continuous updates after
commitment, duplicate packets and mismatched source prefixes. The first fixture
run retained a per-ball failure caused by moving the base before selection;
the corrected fixture moves it only after command receipt. Existing managed
plane and packet-pipeline ROS groups pass. Ten coordinator native cases pass,
including HOME changes and explicit expiry without a prior supported candidate.
These checks do not replace the final clean-source qualification campaign.

## Runner verification boundary

Checked-in model_21800 is incompatible with shared HOME; that attempted probe
and its artifact-validation errors are retained. The unchanged training checkpoint
`hope_training/whole_body_tracking/checkpoints/{policy.onnx,deploy.yaml}` supports
shared HOME and permits actual production PpPolicy inference in memory. It is not
assumed to be the deployed robot artifact. No HAL or robot connection is used.

The original receiver retains an obsolete valid target after invalid input, and
the original policy can subsequently engage it. The optional
`--planner-preengagement-revocation` changes this behavior for shared-HOME schemas
4/5: an identity-bearing invalid packet permanently vetoes that flight for the
current HOME. A final receiver lock spans the policy engagement transition.
The option defaults off, and after-engagement swings still continue.

Tests compare original PR85 production headers, the new option disabled, and the
option enabled against the same ONNX artifact. They cover invalid input before
any valid target, revocation after the policy observes a pending target, and
revocation after engagement. A separate reproduced delivery-order defect required
ordering revocations against their own flight, so a newer unrelated status cannot
hide a delayed veto. That failing counterexample is retained and added to both
native and production-policy tests. Qualification invocation 01 was interrupted
during sanitizer compilation to include this correction before timing campaigns.

## Frozen timing scope

The incoming harness uses independent DOP853 truth, actual camera relays, the
existing adaptive packetizer, PlannerNode, and the production command decoder.
Before offering any ball, it requires the actual planner to acknowledge the
registered HOME/plane. A bounded discovery timeout fails the trial. Invocation
03 retained two failed 300 Hz zero-spin profiles whose first two balls arrived
before HOME discovery; correct production abstention exposed the fixture startup
assumption. The explicit readiness barrier fixes that setup ordering without
excluding any offered ball or changing the ten-flight denominator or thresholds.
Every invocation declares ten flights. Continuous eligibility includes every
offered ball epoch after 100 ms acquisition with more than 30 ms contact lead;
command eligibility uses the ten distinct flight opportunities. Both require
at least 95% coverage. Publication completion age and source-to-decoder P95 must
remain within 30 ms. Full trajectory output is separately capped at 50 Hz.
Stable generations, one immutable command per physical flight, explicit expiry
within 30 ms of its deadline, and complete source-stage ledgers are required.

The full ROS invocation includes 18 profiles: 150/300/360 Hz, three plane modes,
and measured-zero/unknown spin. The separate incoming campaign declares five
repetitions of each profile (90 runs, 900 flights). The original 160-run PR85
campaign retains its original denominators and thresholds, with actual-stage
accounting enabled in every declared run. The diagnostic pair still compares
accounting on/off. No passing retry replaces a declared failure.

The first two development producer-chain trials passed at 150/300 Hz. The 360 Hz
stable-per-ball unknown-spin development trial covered 580/589 eligible epochs
and all ten commands, with 11.659 ms maximum completion age, 9.960 ms decoder
P95 and 3.272 ms maximum expiry notification delay. These development receipts
do not constitute final-source qualification or physical-accuracy evidence.


Qualification 04 retained a 360 Hz fixed/measured-zero failure (546/590
continuous epochs, 9/10 commands) and the outdated scope-inventory check. A relay
callback took 117.596 ms; its cause is unresolved. Ten GC diagnostic trials and
20 publication-mode trials did not reproduce that pause. The latter revealed
three additional asynchronous-DDS command misses with depth-one V2 writers.
Both qualified relay writers now share the explicit bounded input history
(default one, V2 eight); legacy rate-limited outputs retain depth one. Ten
predeclared asynchronous trials after that correction passed all gates, and
12 relay tests passed. These development trials do not replace full qualification
or establish the cause of the original pause. No coverage or freshness threshold
was relaxed. The scope check now records the intended PlannerNode integration
explicitly while retaining every other upstream protected-source byte pin.


Qualification 05 completed the full ladder at `290f7c4`: native 25/25,
sanitized 25/25, parity/numerical gates and 24 actual Runner lifecycle cases
passed. All 18 incoming ROS profiles passed; one existing 150 Hz follow-pose
profile failed (35/41) after a 34 ms source scheduling pause generated six
catch-up exposures within about 1.2 ms. The original repeated campaign passed
157/160, with failures in `integrated_chain_150_FOLLOW_POSE` (repetitions 4 and 5)
and `review_chain_300_12_known` (repetition 4). All three original campaign-failure
profiles passed all five repetitions; the original base-yaw failure profile
passed the full ROS run. The new incoming campaign passed 89/90; a 360 Hz source
pause caused lost input, superseded forecasts and one missing command. These
failures remain blockers; the invocation is not qualified.

The source-pacing correction preserves actual acquisition timestamps and every
offered observation. After a wakeup later than half a period, it resumes a paced
schedule instead of manufacturing catch-up exposures. It records missed nominal
ticks, resynchronizations, actual rate and minimum spacing. An additional source
health gate requires at least 95% of the requested mean rate and at least half a
period between acquisitions. Existing eligibility, command opportunities,
coverage, completion-age and decoder thresholds are unchanged.

A controlled 34 ms source pause reproduced 35/41 coverage before correction.
After correction it produced 35/36: one genuinely acquired post-gap observation
was still rejected because the required bounce was not confirmed. No contact
rule was relaxed. The actual helper repeated 35/36 at 148.91 Hz, and six unit
cases check pacing, source health and failure retention. The first diagnostic
attempt used the wrong multiprocessing start mode and failed initialization;
those unsuccessful setup receipts are also retained. Host CPU-quota counters did
not advance around the long pauses; no quota-throttling cause is claimed.
