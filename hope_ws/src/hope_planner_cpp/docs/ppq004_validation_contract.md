# PPQ004 recorded validation contract

Baseline: `979f9aa`; prior full qualification remains bound to `9603464`.
The machine-readable configuration is `config/ppq004_validation.yaml` (JSON,
which is also YAML). Requirements are in `ppq004_requirements.json`.

This campaign extends validation without adopting a new physics fit or changing
runtime prediction behavior. Parts 1 and 2 are development; part 3 is a previously
inspected benchmark holdout, never a blind generalization test. New physical
capture is outside this implementation; its protocol and missing evidence remain
explicit. Coupled simulation is a separate gate from outgoing-ball replay.

## Independent public-state contract

| Evidence | Public state | Confidence | Strict / managed authority |
| --- | --- | --- | --- |
| Startup, held ball, explicit reset | INVALID | provisional | no command / no command |
| Qualified negative-X flight, incomplete history | OPPONENT_RALLY | provisional | contact eligibility separately / same |
| Qualified positive-X flight, incomplete history | RALLY | provisional | no incoming command / same |
| Negative-X observed striker-side B1 | OPPONENT_SERVE | depends on history | preserve generation and samples / same |
| Positive-X observed striker-side B1 | SERVE | depends on history | preserve generation and samples / same |
| SERVE context or predicted striker B1 only | preceding rally state | no observed-serve credit | route hypothesis only / same |
| Illegal observed contact order | INVALID in strict | not a legal serve | retire / physical tracking may remain, command separately revoked |
| Missing preceding contacts | provisional or unknown | incomplete | never manufacture events / same |
| New qualified physical boundary | direction-qualified state | evidence-dependent | new generation / new generation |
| Direction reversal alone | no new generation | evidence-dependent | cannot invent racket contact / same |
| Invalid identity, source expiry or changed HOME | state and authority separate | evidence-dependent | no new obsolete command / same |

Every legal, forbidden and ambiguous case has a stable case ID in the controlled
suite. Logic fixtures may inject START/CONTACT/CONTEXT; observation replay must
not. Recorded annotations are derived from raw measured geometry, never from
predictor outputs. Same-sensor future positions are recorded-proxy truth.

## Evidence and acceptance

All gates use PASS, FAIL, NOT_RUN, NOT_COVERED or INCONCLUSIVE. No examples is
NOT_COVERED. Missing/truncated observation evidence is INCONCLUSIVE, not a pass.
Reviewed provenance includes source frames, bracketing uncertainty and earliest
causal availability. Ambiguous labels remain in coverage accounting.

Frozen synthetic budgets are 1 mm / 0.5 ms; conversion checks retain 20 mm /
10 ms and 80 ms receiver lead in their original scope. Recorded acceptance
thresholds must be frozen from development data and annotation uncertainty
before candidate holdout scoring. These are different evidence layers.

The accepted 54.731069 ms publication deviation remains a raw failure with a
named disposition; 95% per-observation coverage is diagnostic. Runtime 30 ms
freshness, identity and one-shot rules are unchanged. Every offered eligible
physical flight remains in the denominator even if a packet is rejected correctly.
The seven historical and one fresh retained command losses are unresolved.

## Geometry and clocks

Keep the recorded table-corner coordinates in metres, table surface z=0, and
ball-center contacts near the radius. Never use legacy table-centre extraction.
Source nanoseconds are computed before adding a ROS epoch. Every missing frame
is retained; no interpolated measurement is offered. Quaternion order is XYZW
in the dataset. Identity orientation does not imply measured zero angular velocity.
Base/paddle centroids are not registered robot/control-point poses. Without an
extrinsic, use a named fixture and never claim measured HOME authority.

## Review stages

1. Hashed data adapter, independent annotation schema, state contract.
2. Full-take observation replay and five-state controlled/scoring tests.
3. Separately identified estimator/physics/plane comparisons.
4. Managed conversion, packet faults, actual receiver/Runner checks.
5. Recorded ROS trials, repeatability, complete delivery accounting.
6. Coupled simulation and physical-capture protocol.
7. Clean committed campaign and browsable requirement-to-evidence report.

Generated data, builds and run outputs live outside the checkout. A failed run
is immutable; fixes receive a new invocation directory. Policy/binary/config,
dataset, annotations and scene hashes accompany results.
