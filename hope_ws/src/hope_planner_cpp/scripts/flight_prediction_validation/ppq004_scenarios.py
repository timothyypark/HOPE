"""Bind coupled simulation scenarios to actual decoded native command receipts."""

import argparse
import json
from pathlib import Path
from ppq004_dataset import sha256


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--replay", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--limit", type=int, default=3)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    scenarios = []
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
            file = a.output / f"scenario-{len(scenarios):03}.json"
            file.write_text(json.dumps(scenario, indent=2) + "\n")
            scenarios.append(file.name)
            if len(scenarios) >= a.limit:
                break
        if len(scenarios) >= a.limit:
            break
    (a.output / "manifest.json").write_text(
        json.dumps(
            dict(
                status="PASS" if scenarios else "NOT_COVERED",
                scenarios=scenarios,
                parent_receipt_sha256=sha256(a.replay / "receipt.json"),
            ),
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
