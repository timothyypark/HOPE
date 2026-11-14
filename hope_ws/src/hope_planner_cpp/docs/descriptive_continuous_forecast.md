# Descriptive continuous forecasts

The managed `v2_incoming` backend now keeps conditional physical forecasts
available while shot qualification withholds command authority. The
`V2IncomingCoordinator` enables this policy; standalone `FlightPipeline` users
retain their strict default unless they explicitly enable `descriptive_forecasts`.
This does not enable a live output mode or change the default prediction backend.

## Behavior

Previously, motion-model rejection retired the shot and stopped both CKF
updates and physical forecasts until a qualified new opportunity appeared.
Now the same physical tracker can assimilate subsequent source-qualified
observations while that shot remains rejected. Its existing innovation rejection
and reacquisition rules still apply. A tracking gap over 25 ms resets this
descriptive fit and angular evidence. Six accepted observations spanning at
least 25 ms are required before publishing a descriptive trajectory.

The motion threshold, shot rearm conditions, packet reconciliation, return
eligibility, one-shot ownership and revocation rules are unchanged. A newly
qualified shot resets and seeds the tracker from the original qualified sample
suffix, so descriptive observations cannot leak into an authorized fit.
There is one ball tracker per pipeline; descriptive mode is its inactive-shot
use, rather than a second independent live ball tracker.

Descriptive forecasts retain the rejected shot state/reason and have:

* `physical_available=true` only for a fresh, finite nominal forecast from an
  accepted current measurement; warm-up, rejected measurements and expired
  observations remain unavailable.
* `forecast_status=UNCERTAIN`, `target_valid=false`, and reason
  `DESCRIPTIVE_ONLY:<retained shot reason>`.
* Current position, velocity, covariance, qualified spin when available, and
  trajectory waypoints with the actual source/frame/registration/clock metadata.
* `current_state.linearization_quality=descriptive_conditional_ckf_posterior`.
* Uncertainty provenance containing
  `descriptive_only;motion_model_unqualified;not_command_authority`.
* Candidate `physical_state_available=true` where supported, but
  `command_eligible=false` and `strike_contact_supported=false`.

Covariance remains conditional on the physical model; this change does not
calibrate uncertainty against arbitrary non-ballistic motion. Missing spin is
not relabeled measured zero. Retained shot generations do not establish new
physical racket-contact boundaries. Existing tracker-admission counters still
count strict shot admissions; inspect descriptive forecast availability separately.

The return selector and strike adapter explicitly reject descriptive forecasts,
even if a nominal trajectory crosses the receiving plane. The packet path also
requires an active, matching qualified shot. Publication rejects stale physical
forecasts, including a worker that finishes after its source expires. Source
identity faults and authoritative command revocations retain their existing fences.

## Recorded comparison

The unchanged scoring contract was rerun on all three PPQ004 takes, with no
physics or acceptance threshold tuning. At the 100 ms forecast horizon:

| Split | Available cutoffs before | After | Arcs before | After |
|---|---:|---:|---:|---:|
| Development | 224 / 2018 | 1933 / 2018 | 18 / 151 | 150 / 151 |
| Previously used holdout | 68 / 249 | 243 / 249 | 7 / 17 | 17 / 17 |

The added holdout cutoffs have a median per-arc RMS position error of 21.69 mm,
95th percentile 41.19 mm and worst arc RMS 50.53 mm. The newly covered development
cutoffs have median 22.04 mm, 95th percentile 47.88 mm and worst 107.89 mm.
Different support sets must not be compared as if they were matched accuracy
measurements. These are same-sensor recorded-proxy results on previously seen
screened arcs, not independently qualified legal hitting opportunities.

Every previously available qualified state, original scored error and native
command-eligible target is unchanged across all three recordings and all four
query planes. The extra coverage is descriptive: it does not establish more
authorized racket commands, better native contact accuracy or solved command
recovery. A future change to command recovery needs separate evidence.

Verification passed: all 12 selected ROS/native CTest groups, including real ROS
publication in three plane-reference modes, message serialization, strict
reacquisition and state contracts, return selection, strike adapter/coordinator,
contact corroboration and Runner pre-engagement revocation; all 13 comparison
controls; and the full-recording parity audit. The actual planner executable was
built. This is scoped verification, not a rerun of the complete application or
MuJoCo campaign. The six missing holdout cutoffs are descriptive warm-up;
development retains 80 warm-up and five innovation-rejected cutoffs.

Source implementation: `ae95a3c`; the later ROS regression commit changes tests
only. The comparison contract and parity auditor are on
`analysis/descriptive-forecast-coverage`. Full results, logs and reproduction are
on [the evidence branch](https://github.com/timothyypark/HOPE/tree/evidence/descriptive-forecast-coverage-20261114/descriptive).
