"""Bind coupled simulation scenarios to actual decoded native command receipts."""

import argparse
import copy
import numpy as np
import json
from pathlib import Path
from ppq004_dataset import sha256


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--replay", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--native", type=Path)
    p.add_argument("--limit", type=int, default=3)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    scenarios = []
    extensions = {}
    for path in sorted(a.replay.glob("*.commands.jsonl")):
        for line in path.open():
            command = json.loads(line)
            if not command["published"] or not command["decoded"]:
                continue
            scenario = dict(
                evidence_type="measured_recording",
                transformation="causal estimated state initializes independent coupled simulation",
                command_source_sha256=sha256(path),
                command_source_file=path.name,
                source_index=command["source_index"],
                source_ns=command["source_ns"],
                generation=command["generation"],
                wire=command["wire"],
                contact_lead_s=command["contact_lead_s"],
                ball_position_table=command["initial_belief"][:3],
                ball_velocity=command["initial_belief"][3:],
                ball_spin=[0, 0, 0],
                spin_model="zero-spin conditional plant; no measured zero-spin claim",
                drag_k=0.12861635416914574,
                target_land=[2.055, -0.7625, 0.02],
                landing_tolerance_m=0.2,
                duration_s=5.5,
                repetitions=2,
                base_xy=[command["wire"][3] - 0.58, -0.7625],
                base_yaw_rad=0,
                base_authority="interface_fixture",
                packet_authority="native exact-prefix fixture; no packetizer claim",
            )
            part = int(path.name.split(".")[0][-1])
            data_path = a.source / f"fit/part{part}/raw_extracted.npz"
            data = dict(np.load(data_path))
            times = np.rint(data["t"] * 1e9).astype(np.int64)
            indices = np.flatnonzero(
                data["ball_present"]
                & (times >= command["source_ns"])
                & (times <= command["source_ns"] + int(command["contact_lead_s"] * 1e9))
            )
            scenario["incoming_comparison_only"] = dict(
                truth_kind="recorded_proxy",
                parent_sha256=sha256(data_path),
                source_ns=times[indices].tolist(),
                positions=data["ball_pos"][indices].tolist(),
                note="Future observations are scored after simulation; never applied to ball or controller",
            )
            scenario["recording_id"] = path.name.split(".")[0]
            file = a.output / f"scenario-{len(scenarios):03}.json"
            file.write_text(json.dumps(scenario, indent=2) + "\n")
            scenarios.append(file.name)
            # First decoded command per recording preserves held-out representation.
            break
        if len(scenarios) >= a.limit:
            break
    if scenarios:
        original = json.loads((a.output / scenarios[0]).read_text())
        for name, change in (
            ("yaw", {"base_yaw_rad": 0.25}),
            (
                "translation",
                {"base_xy": [original["base_xy"][0], original["base_xy"][1] + 0.1]},
            ),
            ("moving-base", {"base_velocity_xy": [0.2, 0.0]}),
        ):
            variant = copy.deepcopy(original)
            variant.update(change)
            variant["evidence_type"] = "independent_simulation"
            variant["transformation"] = (
                "Modeled robot "
                + name
                + "; unchanged recorded-prefix world target; plane remains world X"
            )
            path = a.output / ("scenario-" + name + ".json")
            path.write_text(json.dumps(variant, indent=2) + "\n")
            scenarios.append(path.name)
    if a.native:
        import subprocess
        import sys

        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "test"))
        from independent_ball_flight import flight

        for speed, omega in ((12.0, 0.0), (10.0, 180.0)):
            label = "fast" if omega == 0 else "high-spin"
            before, after, bounce = flight(speed, "known", spin_rad_s=omega)
            lines = []
            for index in range(211):
                t = index / 300
                state = before.sol(t) if t < bounce else after.sol(t)
                lines.append(
                    ",".join(
                        map(
                            str,
                            [
                                index,
                                1000000000 + round(t * 1e9),
                                1,
                                *state[:3],
                                1,
                                0,
                                np.sin(state[6] / 2),
                                0,
                                np.cos(state[6] / 2),
                            ],
                        )
                    )
                    + "\n"
                )
            source = a.output / (label + "-observations.csv")
            source.write_text("".join(lines))
            commands = a.output / (label + "-commands.jsonl")
            with (
                (a.output / (label + "-trace.jsonl")).open("w") as out,
                (a.output / (label + "-stderr.log")).open("w") as err,
            ):
                process = subprocess.run(
                    [
                        str(a.native),
                        "--plane-x",
                        ".15",
                        "--forecasts",
                        str(a.output / (label + "-forecasts.jsonl")),
                        "--commands",
                        str(commands),
                    ],
                    input="".join(lines),
                    text=True,
                    stdout=out,
                    stderr=err,
                )
            accepted = (
                [json.loads(line) for line in commands.read_text().splitlines() if line]
                if commands.exists()
                else []
            )
            accepted = [row for row in accepted if row["published"] and row["decoded"]]
            if process.returncode or not accepted:
                extensions[label] = dict(
                    status="FAIL" if process.returncode else "NOT_COVERED",
                    reason="No actual decoded target from synthetic source",
                    exit_code=process.returncode,
                )
                continue
            cmd = accepted[0]
            cutoff = (cmd["source_ns"] - 1000000000) * 1e-9
            state = before.sol(cutoff) if cutoff < bounce else after.sol(cutoff)
            plant_spin = (
                omega
                if cutoff < bounce
                else omega - (after.y[3, 0] - before.y[3, -1]) / ((2.0 / 3) * 0.02)
            )
            scenario = dict(
                evidence_type="independent_simulation",
                transformation="Independent DOP853 synthetic observations through production owner/adapter/packer/receiver",
                command_source_sha256=sha256(commands),
                command_source_file=commands.name,
                source_observations_sha256=sha256(source),
                source_index=cmd["source_index"],
                source_ns=cmd["source_ns"],
                generation=cmd["generation"],
                wire=cmd["wire"],
                contact_lead_s=cmd["contact_lead_s"],
                ball_position_table=state[:3].tolist(),
                ball_velocity=state[3:6].tolist(),
                ball_spin=[0, plant_spin, 0],
                initial_estimated_belief=cmd["initial_belief"],
                spin_model="Explicit simulated angular velocity, no measured-spin claim",
                magnus_k=0.00379260504480258,
                drag_k=0.12861635416914574,
                target_land=[2.055, -0.7625, 0.02],
                landing_tolerance_m=0.2,
                duration_s=5.5,
                repetitions=2,
                base_xy=[cmd["wire"][3] - 0.58, -0.7625],
                base_yaw_rad=0,
                base_authority="interface_fixture",
                packet_authority="native exact-prefix fixture",
            )
            path = a.output / ("scenario-" + label + ".json")
            path.write_text(json.dumps(scenario, indent=2) + "\n")
            scenarios.append(path.name)
            extensions[label] = dict(
                status="PASS", source_speed_mps=speed, source_spin_rad_s=omega
            )

    (a.output / "manifest.json").write_text(
        json.dumps(
            dict(
                status="PASS" if scenarios else "NOT_COVERED",
                scenarios=scenarios,
                extensions=extensions,
                parent_receipt_sha256=sha256(a.replay / "receipt.json"),
            ),
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
