# PPQ004 matched prediction comparison

This diagnostic compares pinned, unchanged native C++ implementations against
future measured PPQ004 positions. Read `contract.json` before interpreting a
score. It is an accuracy comparison, not full-stack qualification.

## Methods

* `main_operator`: latest upstream `LaptopPlayState` observation admission and
  generation/bounce resets, with the packetizer's actual operator preview fit
  (100 ms window, 60 ms minimum span, eight samples, single-flight fitting).
  Future plane queries call its production `FutureContactPredictor` class.
  The operator's advisory-only forecast is omitted because it cannot change
  admission. Its GUI forecast drawing and actual committed packets are not scored.
* `main_batch`: downstream hardware-profile `BatchPhysicsEstimator`, spin
  estimator and `FutureContactPredictor` continuously fed the same take, without
  operator admission. This isolates a useful continuous fit baseline; it is not
  a reproduction of the one-shot packet/receiving-planner execution path.
* `v2_managed`: persistent `V2IncomingCoordinator`, continuous forecasts, and
  native strike-candidate adapter. No annotation-derived lifecycle commands.
  A stable, valid reference and explicit fixed query planes are test fixtures.

Replay includes missing observations and never resets at scoring boundaries.
Both implementations see identical chronological source prefixes. The clock is
virtual and polled at original frame times, rather than actual ROS timer times.
Queries are every six frames (20 ms); this is not a latency benchmark.

## Scores and limitations

Native plane errors use each implementation's actual prediction. The primary
plane is x=0.15 m; other planes are diagnostics declared before the replay.
Measured crossings require two adjacent present samples and a unique crossing
inside an existing incoming contact-free screened arc. Their sampling bracket
is retained in timing error. Missing forecasts are missing coverage, never zero
error. Availability does not mean a command was authorized or executed.

The separate common-kernel diagnostic propagates each estimated position,
velocity and effective spin through identical RK4 free-flight dynamics for
10/30/50/100/150 ms. Its primary horizon is 100 ms. This measures estimated-state
predictive quality under common propagation, not each native full trajectory
algorithm or the CKF filter alone. Spin handling and lifecycle admission differ.

Pairing requires identical source index, arc and query. First compute per-arc
RMS error, then equal-weight arc medians and a paired arc bootstrap. Report
coverage alongside conditional accuracy, including unmatched supported cutoffs.
The source positions are from the same sensor used as input. Existing arc
screening selects smooth ball-flight intervals and can bias results toward
those conditions. These annotations do not establish legal play or physical
contact history. Part 3 is a previously used benchmark holdout, not blind data;
arcs within a single recording do not establish cross-session independence.

## Reproduce

Dependencies: C++17, CMake, Eigen3, yaml-cpp, GTest; Python with NumPy, PyYAML,
pytest, matplotlib. ROS is not required for this standalone native diagnostic.
Use separate clean checkouts at the two SHAs in `contract.json`; commit this
harness before running recordings. No physics/profile tuning is performed.

```bash
cmake -S analysis/ppq004_accuracy -B /tmp/accuracy-build \
  -DMAIN_ROOT=/path/to/upstream-main -DV2_ROOT=/path/to/v2 \
  -DCMAKE_BUILD_TYPE=Release
cmake --build /tmp/accuracy-build -j4
ctest --test-dir /tmp/accuracy-build --output-on-failure
COMPARISON_BUILD=/tmp/accuracy-build MAIN_SOURCE=/path/to/upstream-main \
  python -m pytest -q analysis/ppq004_accuracy/test_comparison.py
python analysis/ppq004_accuracy/run.py \
  --main /path/to/upstream-main --v2 /path/to/v2 \
  --build /tmp/accuracy-build --prepared /path/to/qualification/prepared \
  --output /tmp/accuracy-replay
python analysis/ppq004_accuracy/score.py \
  --replay /tmp/accuracy-replay --source /path/to/qualification/source \
  --annotations /path/to/qualification/annotations/episodes.jsonl \
  --output /tmp/accuracy-scores
```

Inputs are the recovered, verified PPQ004 `prepared/observations.jsonl`, its
manifest, original `source/fit/part{1,2,3}/raw_extracted.npz`, and existing
`annotations/episodes.jsonl`. The runner checks source/profile/binary hashes;
the scorer verifies replay integrity and equality of measured truth with the
replayed positions. Outputs must be fresh directories; failed invocations remain
available. Tests cover causal prefix invariance, quaternion sign equivalence,
configuration loading, pairing, missing support, integration and crossing gaps.
