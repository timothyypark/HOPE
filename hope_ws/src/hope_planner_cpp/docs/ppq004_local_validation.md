# Run the recorded-data campaign

Use the Jazzy/native prerequisites in `v2_local_simulation_guide.md`, plus NumPy
1.26.4, SciPy 1.11.4, Matplotlib, pytest, MuJoCo 3.3.7 and a C++ ONNX Runtime
1.22.0 distribution. The runtime must be compatible with the actual policy files;
retain all binary hashes and version receipts. The cloud reference uses
`ros:jazzy-ros-base` digest
`sha256:00b8d47a6e6384a2834e3d01fa87ae767876543baa574f2d64a75c04ea33c698`.

Commit the checkout first. Keep all output outside it. From the repository root:

```bash
export ORT_ROOT=/absolute/path/onnxruntime-linux-x64-1.22.0
export HOPE_PPQ004_PYTHON=/absolute/path/venv/bin/python
export HOPE_SIMULATION_PYTHONPATH=/absolute/path/venv/lib/python3.12/site-packages
export HOPE_POLICY_PYTHONPATH="$HOPE_SIMULATION_PYTHONPATH"
export HOPE_VERIFICATION_BUILD_JOBS=4
bash hope_ws/src/hope_planner_cpp/scripts/flight_prediction_validation/verify_ppq004.sh \
  /absolute/new/ppq004-campaign
```

The full entry point invokes the retained integrated regression ladder, then
recorded preparation, independent annotation inventory, strict/managed replay,
spin/physics ablations, source-causal scoring, command fixtures, recorded ROS
profiles (five fresh processes per rate/plane profile), source/transport faults,
full-take bounded-memory runs, actual Runner checks and dynamic MuJoCo cases.
Hardware is never activated. The current qualification is expected to remain
incomplete where measured coverage, command availability or modeled execution
fails. Inspect `results.json` and `index.html`; exit 1 is not permission to discard
or overwrite failed receipts.

For a development iteration only, append `--development --skip-integrated`.
That executes one short recorded ROS profile and records the full regression
ladder as NOT_RUN. It cannot replace final qualification.

## Individual stages

`ppq004_prepare.py` consumes the verifier's new unpack directory and preserves
every source frame in JSONL. `ppq004_replay.py` invokes the native
`hope_ppq004_state_replay`, one owner per recording, with virtual expiry through
missing frames. Its default run has no command packets; `--command-fixtures`
explicitly enables direct native packet queries and the actual schema-4 receiver.
These fixtures cannot establish packetizer delivery. The ROS harness supplies
that separate path via `--recorded-observations` and `--recording-id`.

`--position-only`, `--set key=value`, `--plane-x` and `--forecast-stride` are
explicit replay options retained in receipts. Recorded state annotations never
enter either predictor. They enter `state_machine_scoring.py` with an explicit
recording ID. The four reviewed public-serve intervals do not prove complete
legal serves, racket boundaries, or independent physical accuracy.

`compare_recordings.py --recorded-proxy` permits same-sensor proxy evaluation
without opening independent Gate P. Its fixed-plane and physics arguments are
shared explicitly across comparison binaries. Legacy one-shot remains sparse
at its real triggers; no missing one-shot trajectory is fabricated.

## Coupled simulation

`build_ppq004_policy_bridge.sh` builds a software-only bridge to the actual
PpPolicy, ONNX and decoder. `ppq004_scenarios.py` binds scenarios to real native
command receipts and causal state estimates. `ppq004_coupled_simulation.py`
initializes the independently stepped ball and dynamic robot once, supplies joint
and body/torso feedback, applies policy torques through the model actuators, and
records actual contact impulses. It never pins robot joints during execution or
forces a collision. A miss, failed engagement or fall remains FAIL.

The supplied scene's impact law differs from the managed analytic racket law;
its physics receipt is explicit. Unknown measured spin uses a declared zero-spin
conditional plant, not a claim of measured zero spin. Dynamic contact, landing,
balance and successive-ball recovery are distinct gates. See
`ppq004_physical_protocol.md` for evidence that simulation cannot supply.
