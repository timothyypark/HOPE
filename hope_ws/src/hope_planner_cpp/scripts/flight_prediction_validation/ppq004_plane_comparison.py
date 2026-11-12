"""Short-prefix public-method diagnostic; never resets the full-take owner replay.

Crossings and local derivative sensitivity use future observations only here in
scoring. A bracket gives an occurrence interval, not sub-frame physical truth.
"""

import argparse
import json
from pathlib import Path
import subprocess
import sys
import numpy as np
from ppq004_dataset import sha256


def dataset(source, episodes, plane, code_sha):
    data = dict(np.load(source / "fit/part3/raw_extracted.npz"))
    times = np.rint(data["t"] * 1e9).astype(np.int64)
    positions = data["ball_pos"]
    flights = []
    unsupported = []
    for arc in episodes:
        if arc["recording_id"] != "ppq004_part3":
            continue
        begin, end = arc["source_frames"]
        crossings = [
            i
            for i in range(begin, end)
            if data["ball_present"][i : i + 2].all()
            and (positions[i, 0] - plane) * (positions[i + 1, 0] - plane) < 0
        ]
        if len(crossings) != 1:
            unsupported.append(
                dict(
                    arc_id=arc["physical_flight_id"],
                    reason="No unique measured crossing bracket",
                )
            )
            continue
        i = crossings[0]
        derivatives = []
        for radius in (2, 3, 4):
            indices = np.arange(i - radius, i + radius + 2)
            if (
                indices[0] < begin
                or indices[-1] > end
                or not data["ball_present"][indices].all()
            ):
                continue
            t = (times[indices] - times[i]) * 1e-9
            derivatives.append(np.polyfit(t, positions[indices], 1)[0])
        if len(derivatives) != 3:
            unsupported.append(
                dict(
                    arc_id=arc["physical_flight_id"],
                    reason="Insufficient contact-free local derivative windows",
                )
            )
            continue
        fraction = (plane - positions[i, 0]) / (positions[i + 1, 0] - positions[i, 0])
        arrival = int(round(int(times[i]) + fraction * int(times[i + 1] - times[i])))
        truth = positions[i] + fraction * (positions[i + 1] - positions[i])
        observations = []
        for index in range(begin, i + 1):
            if not data["ball_present"][index]:
                continue
            q = data["ball_quat"][index]
            orientation = bool(np.isfinite(q).all() and np.linalg.norm(q) > 1e-9)
            observations.append(
                dict(
                    source_ns=int(times[index]),
                    position=positions[index].tolist(),
                    quaternion_xyzw=q.tolist() if orientation else None,
                    orientation_available=orientation,
                    orientation_authoritative=orientation,
                    omega_valid=False,
                )
            )
        if len(observations) < 4:
            unsupported.append(
                dict(
                    arc_id=arc["physical_flight_id"],
                    reason="Insufficient causal prefix",
                )
            )
            continue
        flights.append(
            dict(
                session_id="ppq004_part3",
                ball_id="Ball",
                flight_id=arc["physical_flight_id"],
                physical_boundary_qualified=False,
                split="held_out",
                direction=1 if arc["direction"] == "positive" else -1,
                complete_history=False,
                source_frames=[begin, end],
                observations=observations,
                truth_events=[
                    dict(
                        kind="receiving_plane",
                        event_id=arc["physical_flight_id"] + f":plane:{plane}",
                        position=truth.tolist(),
                        arrival_ns=arrival,
                        velocity=derivatives[1].tolist(),
                        source_frames=[i, i + 1],
                        occurrence_interval_ns=[int(times[i]), int(times[i + 1])],
                        derivative_windows_samples=[6, 8, 10],
                        derivative_window_sensitivity_mps=float(
                            np.max(
                                np.linalg.norm(
                                    np.asarray(derivatives) - derivatives[1], axis=1
                                )
                            )
                        ),
                        truth_kind="recorded_proxy",
                        physical_velocity_qualified=False,
                    )
                ],
            )
        )
    return dict(
        evidence_type="measured_recording",
        independent_truth=False,
        frame_id="table",
        registration_receipt_sha256=sha256(source / "fit/part3/raw_extracted.npz"),
        clock_mapping_id="ppq004_part3_integer_epoch_0",
        x_hit=plane,
        code_pins={
            m: code_sha for m in ("legacy_one_shot", "progressive_batch", "v2_ckf")
        },
        scope="Short-prefix diagnostic with explicit RESTART and unknown history; separate from observation-only persistent managed replay",
        velocity_scope="Local same-sensor derivative proxy; sensitivity retained, not physical velocity qualification",
        flights=flights,
        unavailable_crossings=unsupported,
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in (
        "source",
        "annotations",
        "v2-executable",
        "baseline-executable",
        "output",
    ):
        p.add_argument("--" + key, type=Path, required=True)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    script = Path(__file__).with_name("compare_recordings.py")
    code = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    episodes = [json.loads(line) for line in a.annotations.read_text().splitlines()]
    gates = {}
    for plane in (0.15, -0.58):
        key = f"plane_{plane}"
        value = dataset(a.source, episodes, plane, code)
        path = a.output / (key + ".json")
        path.write_text(json.dumps(value, indent=2) + "\n")
        if not value["flights"]:
            gates[key] = dict(
                status="NOT_COVERED",
                reason="No supported measured crossing and local derivative",
            )
            continue
        with (a.output / (key + ".log")).open("w") as log:
            proc = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--dataset",
                    str(path),
                    "--v2-executable",
                    str(a.v2_executable),
                    "--baseline-executable",
                    str(a.baseline_executable),
                    "--recorded-proxy",
                    "--output",
                    str(a.output / key),
                ],
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        gates[key] = dict(
            status="PASS" if proc.returncode == 0 else "FAIL",
            arcs=len(value["flights"]),
            unavailable=len(value["unavailable_crossings"]),
            exit_code=proc.returncode,
        )
    (a.output / "results.json").write_text(
        json.dumps(
            dict(
                status="FAIL"
                if any(g["status"] == "FAIL" for g in gates.values())
                else "PASS"
                if any(g["status"] == "PASS" for g in gates.values())
                else "NOT_COVERED",
                scope="Public-method recorded-proxy comparison execution; not adoption or physical Gate P",
                gates=gates,
            ),
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
