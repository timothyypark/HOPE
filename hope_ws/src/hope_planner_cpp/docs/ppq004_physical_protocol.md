# Physical evidence handoff (not executed by the cloud campaign)

The authorized cloud scope is software and simulation. Every hardware gate stays
NOT_RUN until a separate physical invocation supplies the evidence below. No
script in this campaign connects to HAL or enables a robot.

## Before capture

Record robot, racket, ball and camera identities; scene/table registration with
uncertainty; marker-to-base and paddle-marker-to-control-point extrinsics; HOME
reference epoch; effective physics; exact source/build/policy/config hashes.
Verify the table-corner convention, positive X toward the opponent, ball-center
radius above z=0, XYZW/WXYZ conversion and the single 0.76 m policy offset.
Record acquisition/receipt clocks and measured cross-host mapping uncertainty.
A moving base must retain registered pose freshness and timestamped orientation;
yaw must not silently rotate the world-X hitting plane.

## Capture schedule

Use new sessions, distinct from PPQ004 parts 1–3. Start with at least twenty
independent reviewed episodes in each valid public state and twenty invalid
examples spanning declared fault families. These are collection targets, not
statistical qualification. Reserve untouched sessions for final generalization.
Prioritize outgoing serves, absent from the current holdout candidates. Include
both rally directions, incoming serves, complete launch-to-contact histories,
10–12 m/s balls, measured spin variation, rotated/moving bases, gaps, reacquisition,
net/ground/second-bounce negatives and successive-ball recovery.

## Per-episode evidence

Retain raw ball/base/paddle markers and validity, original frame indices, source
and receipt clocks, registration receipts, reviewed boundary/contact intervals,
all commands and decoder receipts, pending/engaged/revoked Runner transitions,
actual joint positions/velocities, delivered actuator commands, and independent
contact/landing observations. Identify the physical flight independently of all
internal generations and packet attempts. Document operator interventions.

Use bracketing frames and independent measurement uncertainty for contact and
landing timing; do not treat a fitted midpoint as exact truth. Annotators must
not use predictor classifications as expected labels. Review full event order,
not only a striker-side bounce. Record rejected and ambiguous candidates too.

## Acceptance and reporting

Freeze physical tolerances and sample size from uncertainty/failure-rate needs
before opening held-out sessions. Record per-state/transition coverage, racket
contact, net clearance, landing, balance and recovery independently. A command
rejection can obey the authority contract while losing a valid opportunity.
Do not remove that flight from the denominator. Synthetic/recorded-proxy passes
cannot populate physical gates. Keep missing registrations and class support
NOT_COVERED; unresolved labels INCONCLUSIVE; unexecuted captures NOT_RUN.
