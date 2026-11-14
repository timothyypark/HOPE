# Reproduce the comparison

Use the [source harness](https://github.com/timothyypark/HOPE/tree/analysis/ppq004-main-ckf-accuracy/analysis/ppq004_accuracy)
at `9e5b0d7` (the replay/scorer code is unchanged from the prereplay `f6c33a4`).
Dependencies are C++17/CMake/Eigen3/yaml-cpp/GTest and Python NumPy/PyYAML/pytest/
matplotlib. The recorded invocation used the existing ROS Jazzy container but
this standalone diagnostic does not require a running ROS graph.

## Re-score the retained native outputs

Clone the source and evidence branches into separate directories. From the
source checkout, unpack the original archived recordings to a new directory:

```bash
export PYTHONDONTWRITEBYTECODE=1
python calibration/ppq004_20261020/verify_dataset.py --unpack /tmp/accuracy-source
```

From this evidence checkout, verify the package and restore replay files:

```bash
cd comparison
sha256sum -c SHA256SUMS
mkdir /tmp/accuracy-replay
cp replay/freeze.json replay/receipt.json /tmp/accuracy-replay/
for path in replay/*.gz; do
  gzip -dc "$path" > "/tmp/accuracy-replay/$(basename "$path" .gz)"
done
```

Then run the scorer from the source checkout, replacing `/path/to/evidence`:

```bash
python analysis/ppq004_accuracy/score.py \
  --replay /tmp/accuracy-replay --source /tmp/accuracy-source \
  --annotations /path/to/evidence/comparison/inputs/episodes.jsonl \
  --output /tmp/accuracy-scores
python analysis/ppq004_accuracy/plot.py \
  --results /tmp/accuracy-scores/results.json --output /tmp/accuracy-plots
python analysis/ppq004_accuracy/diagnose.py \
  --replay /tmp/accuracy-replay --source /tmp/accuracy-source \
  --annotations /path/to/evidence/comparison/inputs/episodes.jsonl \
  --output /tmp/accuracy-scores/availability-reasons.json
```

The scorer checks native output and input hashes against the original receipt,
exact query denominators, and equality of replayed ball positions/timestamps
with the original NPZ truth. On the recorded environment the restored archive
reproduces the three primary score files byte for byte; see
`artifact-recheck.json`. `compression.json` also records uncompressed hashes.

## Rebuild and rerun both implementations

From the source checkout, create clean pinned worktrees:

```bash
git fetch https://github.com/hitchopen/HOPE.git main
git worktree add --detach /tmp/accuracy-main 01de418c146cf3f2d2dba32e63b425f01c8a7f19
git worktree add --detach /tmp/accuracy-v2 f4902023d49c85ff57da62a618b2001181d3b8e7
python /tmp/accuracy-v2/hope_ws/src/hope_planner_cpp/scripts/flight_prediction_validation/ppq004_prepare.py \
  --source /tmp/accuracy-source \
  --archive /tmp/accuracy-v2/calibration/ppq004_20261020 \
  --output /tmp/accuracy-prepared
cmake -S analysis/ppq004_accuracy -B /tmp/accuracy-build \
  -DMAIN_ROOT=/tmp/accuracy-main -DV2_ROOT=/tmp/accuracy-v2 -DCMAKE_BUILD_TYPE=Release
cmake --build /tmp/accuracy-build -j4
ctest --test-dir /tmp/accuracy-build --output-on-failure
COMPARISON_BUILD=/tmp/accuracy-build MAIN_SOURCE=/tmp/accuracy-main \
  python -m pytest -q -o cache_dir=/tmp/accuracy-pytest-cache analysis/ppq004_accuracy/test_comparison.py
python analysis/ppq004_accuracy/run.py \
  --main /tmp/accuracy-main --v2 /tmp/accuracy-v2 --build /tmp/accuracy-build \
  --prepared /tmp/accuracy-prepared --output /tmp/accuracy-fresh-replay
```

Run the scorer against `/tmp/accuracy-fresh-replay` into another new score
directory. A new run has its own receipt and binary hashes; do not overwrite the
retained evidence. `binaries/*.gz` preserves the original built adapters for
audit, not as a portable installation recommendation. Source and configuration
must remain unchanged; the runner enforces clean pinned implementation checkouts.
For a container with different file ownership, explicitly mark only these trusted
worktrees as Git safe directories. Do not disable ownership checks globally.

The prepared episode file is deliberately empty. Always use the retained
`inputs/episodes.jsonl` for these exact scores. It contains screened arcs with
incomplete physical history; it is not a set of qualified legal-play labels.
