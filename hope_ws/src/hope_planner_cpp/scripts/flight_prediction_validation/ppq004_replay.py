"""Stream prepared full takes into the real native observation-only implementation."""

import argparse
import json
from pathlib import Path
import subprocess
from ppq004_dataset import sha256


def replay(
    prepared,
    executable,
    output,
    profile="managed",
    spin=True,
    sets=(),
    forecast_stride=6,
    plane_x=0.15,
    command_fixtures=False,
):
    prepared, executable, output = map(Path, (prepared, executable, output))
    manifest = json.loads((prepared / "manifest.json").read_text())
    if sha256(prepared / "observations.jsonl") != manifest["files"]["observations.jsonl"]:
        raise ValueError("prepared observations changed")
    output.mkdir(parents=True, exist_ok=False)
    receipt = dict(
        schema="ppq004-native-replay-v1",
        evidence_type="measured_recording",
        input_manifest_sha256=sha256(prepared / "manifest.json"),
        binary_sha256=sha256(executable),
        profile=profile,
        orientation_forwarded=spin,
        physics_overrides=list(sets),
        command_fixtures=command_fixtures,
        plane={"mode": "fixed", "x": plane_x, "authority": "interface_fixture"},
        runs=[],
    )
    current = None
    process = None
    log = None
    error = None
    frames = 0
    try:
        with (prepared / "observations.jsonl").open() as observations:
            for line in observations:
                row = json.loads(line)
                recording = row["recording_id"]
                if recording != current:
                    if process is not None:
                        process.stdin.close()
                        code = process.wait()
                        log.close()
                        error.close()
                        receipt["runs"].append(
                            dict(recording_id=current, frames=frames, exit_code=code)
                        )
                        if code:
                            raise RuntimeError("native replay failed; retain stderr")
                    current = recording
                    frames = 0
                    log = (output / f"{recording}.trace.jsonl").open("w")
                    error = (output / f"{recording}.stderr").open("w")
                    command = [
                        str(executable),
                        "--profile",
                        profile,
                        "--plane-x",
                        str(plane_x),
                        "--forecasts",
                        str(output / f"{recording}.forecast.jsonl"),
                        "--forecast-stride",
                        str(forecast_stride),
                    ]
                    for setting in sets:
                        command += ["--set", setting]
                    if command_fixtures:
                        command += ["--commands", str(output / f"{recording}.commands.jsonl")]
                    process = subprocess.Popen(
                        command, stdin=subprocess.PIPE, stdout=log, stderr=error, text=True
                    )
                ball = row["streams"]["ball"]
                position = ball["position_m"] or [0, 0, 0]
                quaternion = ball["quaternion_xyzw"] or [0, 0, 0, 1]
                values = [
                    row["source_index"],
                    row["source_time_ns"],
                    int(ball["available"]),
                    *position,
                    int(spin and ball["orientation_available"]),
                    *quaternion,
                ]
                process.stdin.write(",".join(map(str, values)) + "\n")
                frames += 1
        if process is not None:
            process.stdin.close()
            code = process.wait()
            log.close()
            error.close()
            receipt["runs"].append(dict(recording_id=current, frames=frames, exit_code=code))
            if code:
                raise RuntimeError("native replay failed")
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            process.wait()
        if log and not log.closed:
            log.close()
        if error and not error.closed:
            error.close()
        receipt["files"] = {p.name: sha256(p) for p in output.iterdir() if p.is_file()}
        (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--prepared", type=Path, required=True)
    p.add_argument("--executable", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--profile", choices=["strict", "managed"], default="managed")
    p.add_argument("--position-only", action="store_true")
    p.add_argument("--set", action="append", default=[])
    p.add_argument("--forecast-stride", type=int, default=6)
    p.add_argument("--plane-x", type=float, default=0.15)
    p.add_argument(
        "--command-fixtures",
        action="store_true",
        help="Explicit native packet fixtures; not actual packetizer delivery",
    )
    a = p.parse_args()
    replay(
        a.prepared,
        a.executable,
        a.output,
        a.profile,
        not a.position_only,
        a.set,
        a.forecast_stride,
        a.plane_x,
        a.command_fixtures,
    )


if __name__ == "__main__":
    main()
