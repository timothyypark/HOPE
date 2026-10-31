# Draft PR: Add V2 flight prediction and integrated shadow planning

Target: `hitchopen/HOPE:nightly_built`  
Source: `timothyypark:feature/v2-incoming-validity-continuous-dropin`

[Open the upstream comparison](https://github.com/hitchopen/HOPE/compare/nightly_built...timothyypark:feature/v2-incoming-validity-continuous-dropin?expand=1). Use the title above and the body below, then choose **Create draft pull request**. Automated creation was rejected with HTTP 403 (`Resource not accessible by integration`); this document is a prepared draft, not an opened upstream PR.

---

Introduces opt-in V2 flight prediction and integrated shadow planning, including a managed incoming path that shares one authoritative flight history between continuous forecasts and immutable racket commands. Invalid trajectory evidence retires pending authority and produces identity-bearing revocation. The managed incoming path supplies the existing racket planner through a source-causal `StrikeTarget` adapter.

**Draft for review; delivery qualification remains incomplete.** Seven historical lost-flight cases and one fresh case remain confirmed. The latest incoming campaign delivered usable commands for 899/900 independently offered flights. Hardware and physical deployments are outside this iteration's acceptance scope.

## Scope and relationship to existing PRs

Base: `hitchopen/HOPE:nightly_built` at `91aecabfd44cb258ac998158e724be9017d883a7`.
Head: `timothyypark:feature/v2-incoming-validity-continuous-dropin` at `0f17cab2f19852b262fb148d88387755c1d38213`.

This is the cumulative upstream proposal: **213 changed files and 93 commits** at creation, including substantial retained documentation, fixtures and qualification results. It includes the still-open #85 at `4d2247c`, followed by 35 commits. It does not close #85. Reviewers should coordinate the overlapping merge order; if #85 merges first, reassess the remaining diff and base before merging this PR.

[Fork PR #1](https://github.com/timothyypark/HOPE/pull/1) remains the narrower review of the V2 incoming milestone against the PR85 branch. `nohope` is unchanged.

## Resulting behavior

- Adds typed observation, context, event, prediction and candidate interfaces; probabilistic tracking, event forecasts, trusted-spin handling and physical-flight reacquisition.
- Includes the PR85 integrated shadow backend, base/HOME/plane contracts, bounded ingress and independent outgoing numerical validation.
- Adds the managed V2 incoming backend, sharing causal history between continuous predictions and one immutable command per committed flight. Exact packet-prefix matching, source expiry and HOME/plane identity remain enforced.
- Adds a default-off production Runner option that vetoes a revoked flight before engagement. An already engaged swing continues under the existing contract.
- Corrects lifecycle verification using complete source/generation-matched transition records, with bounded default-off instrumentation and negative controls.
- Adds per-flight outcome accounting, independent conversion simulation, actual decoder checks, supplied A3 MuJoCo outgoing-flight replay and reviewable trajectory plots.

Legacy remains the default. The existing managed racket planner and schema 4/5 formats remain unchanged. The incoming path does not enable mid-swing retargeting or active-swing cancellation.

## Verification actually completed

The frozen full run used source `96034645f26b1597c093281a398fa0e62d5c93b5` in ROS Jazzy on Ubuntu 24.04. The final head adds only result reports and their scope inventory. Upstream `nightly_built` still matches the tested baseline; the head contains that baseline without divergent base commits. These are recorded local qualification results, not a claim that GitHub CI passed.

| Check | Result |
|---|---|
| Native C++ / ASan, UBSan and leaks | 25/25 groups each pass |
| Independent outgoing numerical reference | 144/144 pass |
| Current and historical legacy parity | 701/701 each pass |
| V2 cutoff comparison | 789 checked: 782 exact, seven pinned conservative contact-confirmation delays |
| Full registered ROS suite | Planner 131/132, messages 2/2, bringup 25/27 |
| Existing-backend campaign | 155/160 raw passes; 1,440/1,440 flights receive usable decoded targets |
| Incoming campaign | 88/90 raw passes; 899/900 flights receive usable decoded targets |
| Conversion simulation | 162/162 checks; all 81 physical scenarios covered |
| Supplied MuJoCo outgoing-ball replay | 159/159 pass |
| Lifecycle consumers / historical failure replays | 14/14 and 2/2 pass |
| Lifecycle tracing on/off comparison | 4/4 comparisons pass |
| Actual Runner/ONNX baseline-disabled-enabled comparison | 24/24 expected outcomes pass |
| Actual recorded-command Runner replay | 4/4 pass, including valid-only controls |

The ROS planner failure and one existing-backend campaign failure concern startup cadence before the scored flights. Four campaign failures concern skipped observation updates whose targets remain valid through contact. Bringup flake8/pep257 failures are inherited, with zero added signatures. The original failed verdicts and all declared repetitions remain retained.

The revised acceptance policy accepts the historical 54.731069 ms forecast-publication deviation and treats per-observation coverage as diagnostic. Runtime freshness and invalidation are unchanged. The new 41.784759 ms forecast delay affected a command-ineligible, already-committed flight; replay of its actual command showed engagement before revocation. That raw timing failure remains recorded.

## Remaining merge blocker

The incoming path still loses usable opportunities when packet formation or delivery fails, typed history is incomplete, or an immutable packet expires before processing. In the fresh failure, all ten packets formed, but three samples in flight 9's exact prefix were typed-published by the relay and never recorded at the planner. The prefix guard correctly rejected the packet; the flight still lost its only usable command.

A verified remedy remains required. Any pre-command recovery must preserve bounded memory, exact causal prefixes, HOME/plane identity, expiry, invalidation and at most one published command per physical flight. No such recovery is enabled in this PR. Preserve the seven historical failures and demonstrate targeted failing-before/passing-after cases before rerunning the affected qualification gates.

## Simulation boundaries and evidence

MuJoCo ran the supplied scene with the robot pinned, starting the outgoing ball at the converted contact with reconstructed impact velocity. The recorded Runner replays used production policy/ONNX with stand-state feedback and rebased clocks/HOME epochs. These establish numerical conversion, outgoing ball flight and the tested software lifecycle; they do not establish dynamic robot swings, racket collisions or measured physical accuracy.

- [Current assessment and individual findings](https://github.com/timothyypark/HOPE/blob/feature/v2-incoming-validity-continuous-dropin/hope_ws/src/hope_planner_cpp/docs/v2_simulation_verification_results.md)
- [Machine-readable qualification summary](https://github.com/timothyypark/HOPE/blob/feature/v2-incoming-validity-continuous-dropin/hope_ws/src/hope_planner_cpp/docs/v2_simulation_verification_results.json)
- [Raw evidence, all failure dispositions, checksums and plots](https://github.com/timothyypark/HOPE/tree/evidence/v2-simulation-verification-20261030)
- [Preserved original qualification evidence](https://github.com/timothyypark/HOPE/tree/evidence/v2-incoming-qualification-20261029)
