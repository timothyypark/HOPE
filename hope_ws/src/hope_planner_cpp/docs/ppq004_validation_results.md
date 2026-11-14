# PPQ004 validation recovery and current status

The implementation was recovered from the published
`feature/ppq004-recorded-validation` branch at
`55799d4d31638c98c8b555549f56f11fc62ead59`. The previous workspace, unpushed
commits and November 12 raw campaign outputs were not present in the restored
cloud environment on November 14. No recoverable container, Docker volume,
Git object, bundle or shared-file copy was found; the available environment tools
do not expose a workspace snapshot restore operation.

The three missing code fixes were reconstructed from the recorded edits:
explicitly unavailable camera quaternions and actual Ball timestamp duplication;
full third-take exposure around the first command for decoder/process delay
faults; and fault-response requirements for spin qualification. These are new
commits, not recovered original commit objects. Runtime prediction, physics,
30 ms freshness and command authority have not been changed.

## Evidence policy

The archived recordings, hashes, reviewed state annotations, thresholds,
controlled tests and campaign implementation survived in Git. They are the basis
for a new full verification invocation. Older October evidence branches also
remain available for historical lost-flight audits. New November 14 results must
carry their own source SHA, environment versions and receipt hashes.

The November 12 chat reported native/sanitizer passes, five registered ROS
failures, conditional holdout accuracy/classification gaps, eight failed coupled
scenarios and one uncovered worker-completion exposure. Those statements remain
historical context; absent raw receipts are not represented as recovered or
reissued under their original identities. Fresh results will supersede this
in-progress status without erasing the reported earlier failures.

## Current execution

Reconstruction is committed and the full software campaign is being rebuilt.
Qualification is not yet established. Hardware remains protocol-only and
NOT_RUN. The campaign evaluates all five public states, persistent recorded
prediction, actual ROS delivery/decoding and actual policy-driven simulation as
separate evidence layers. Passing synthetic logic does not fill missing measured
state classes or establish physical accuracy.

Follow [the reproduction guide](ppq004_local_validation.md). The source is
`feature/ppq004-recorded-validation`; new recovery evidence is published on
`evidence/ppq004-validation-20261114` in `timothyypark/HOPE`.
