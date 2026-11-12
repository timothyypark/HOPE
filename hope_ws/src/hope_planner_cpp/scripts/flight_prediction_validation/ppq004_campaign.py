"""Frozen PPQ004 campaign. Independent failed gates do not erase later evidence."""

import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
from ppq004_dataset import sha256
from ppq004_report import report, requirement_results


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument(
        "--development",
        action="store_true",
        help="One short ROS trial; not final qualification",
    )
    p.add_argument(
        "--skip-integrated",
        action="store_true",
        help="Development only; retain NOT_RUN full regression gate",
    )
    a = p.parse_args()
    root = a.output.resolve()
    repo = Path(__file__).resolve().parents[5]
    package = repo / "hope_ws/src/hope_planner_cpp"
    scripts = package / "scripts/flight_prediction_validation"
    if subprocess.check_output(
        ["git", "-C", str(repo), "status", "--porcelain"], text=True
    ).strip():
        raise SystemExit(
            "Commit the candidate before a campaign; dirty source is not qualification"
        )
    root.mkdir(parents=True, exist_ok=False)
    config = json.loads((package / "config/ppq004_validation.yaml").read_text())
    campaign = dict(
        source_sha=subprocess.check_output(
            ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
        ).strip(),
        config=config,
        config_sha256=sha256(package / "config/ppq004_validation.yaml"),
        python=sys.version,
        platform=platform.platform(),
        development=a.development or a.skip_integrated,
        annotation_sha256=sha256(
            package / "test/fixtures/ppq004/reviewed_intervals.jsonl"
        ),
        physical_scope="protocol_only",
        started_ns=time.time_ns(),
    )
    (root / "campaign.json").write_text(json.dumps(campaign, indent=2) + "\n")
    results = dict(campaign=campaign, gates={})
    py = sys.executable

    def save():
        (root / "results.json").write_text(json.dumps(results, indent=2) + "\n")

    def run(name, command, evidence="interface_fixture", requires=()):
        if any(results["gates"].get(r, {}).get("status") != "PASS" for r in requires):
            results["gates"][name] = dict(
                status="NOT_RUN",
                evidence_type=evidence,
                reason="Prerequisite failed: " + ",".join(requires),
            )
            save()
            return False
        start = time.monotonic()
        print("START", name, flush=True)
        with (root / (name + ".log")).open("w") as log:
            log.write(json.dumps(list(map(str, command))) + "\n")
            log.flush()
            try:
                process = subprocess.run(
                    list(map(str, command)),
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    cwd=repo,
                )
            except OSError as error:
                log.write(f"Cannot execute gate: {error}\n")
                process = subprocess.CompletedProcess(command, 127)
        results["gates"][name] = dict(
            status="PASS" if process.returncode == 0 else "FAIL",
            exit_code=process.returncode,
            evidence_type=evidence,
            log=name + ".log",
            duration_s=time.monotonic() - start,
            command=list(map(str, command)),
        )
        for receipt in (
            root / name / "result.json",
            root / name / "results.json",
            root / name / "manifest.json",
        ):
            if receipt.exists():
                value = json.loads(receipt.read_text())
                verdict = value.get("status", value.get("verdict"))
                if verdict in (
                    "PASS",
                    "FAIL",
                    "NOT_RUN",
                    "NOT_COVERED",
                    "INCONCLUSIVE",
                ):
                    results["gates"][name]["execution_status"] = results["gates"][name][
                        "status"
                    ]
                    results["gates"][name]["status"] = verdict
        save()
        print("RESULT", name, process.returncode, flush=True)
        return process.returncode == 0

    archive = repo / "calibration/ppq004_20261020"
    run(
        "data-integrity",
        [py, archive / "verify_dataset.py", "--unpack", root / "source"],
        "measured_recording",
    )
    run(
        "prepare",
        [
            py,
            scripts / "ppq004_prepare.py",
            "--source",
            root / "source",
            "--archive",
            archive,
            "--output",
            root / "prepared",
        ],
        "measured_recording",
        ("data-integrity",),
    )
    run(
        "archived-benchmark",
        [
            py,
            scripts / "ppq004_reference_check.py",
            "--tools",
            archive / "tools",
            "--fit",
            root / "source/fit",
            "--output",
            root / "archived-benchmark",
        ],
        "measured_recording",
        ("data-integrity",),
    )
    run(
        "annotations",
        [
            py,
            scripts / "ppq004_annotations.py",
            "--source",
            root / "source",
            "--tools",
            archive / "tools",
            "--output",
            root / "annotations",
        ],
        "measured_recording",
        ("data-integrity",),
    )
    run(
        "scorer-controls",
        [
            py,
            "-m",
            "pytest",
            "-q",
            package / "test/test_ppq004_dataset.py",
            package / "test/test_state_machine_scoring.py",
            package / "test/test_scoped_accuracy.py",
        ],
    )
    if not a.skip_integrated:
        run(
            "integrated-regression",
            ["bash", scripts / "verify_integrated.sh", root / "integrated"],
        )
        for path in sorted((root / "integrated").glob("*.exit")):
            code = int(path.read_text())
            results["gates"]["integrated/" + path.stem] = dict(
                status="NOT_RUN" if code == 77 else "PASS" if code == 0 else "FAIL",
                evidence_type="interface_fixture",
                exit_code=code,
                log="integrated/" + path.stem + ".log",
            )
        save()
        native = root / "integrated/native"
        ros = root / "integrated"
    else:
        results["gates"]["integrated-regression"] = dict(
            status="NOT_RUN",
            reason="Explicit development invocation",
            evidence_type="interface_fixture",
        )
        save()
        native = root / "native"
        ros = root / "ros"
        run(
            "native-configure",
            [
                "cmake",
                "-S",
                package / "test/native",
                "-B",
                native,
                "-DCMAKE_BUILD_TYPE=Release",
            ],
        )
        run(
            "native-build",
            ["cmake", "--build", native, "-j4"],
            requires=("native-configure",),
        )
        run(
            "native-test",
            ["ctest", "--test-dir", native, "--output-on-failure"],
            requires=("native-build",),
        )
        run(
            "ros-build",
            [
                "bash",
                "-c",
                'source /opt/ros/jazzy/setup.bash && MAKEFLAGS=-j4 colcon --log-base "$1/log" build --base-paths "$2/hope_ws/src" "$2/NatNet2ROS2/src/motion_capture_tracking_interfaces" --build-base "$1/build" --install-base "$1/install" --packages-select hope_msgs hope_planner_cpp hope_bringup motion_capture_tracking_interfaces --executor sequential --cmake-args -DBUILD_TESTING=ON -DCMAKE_BUILD_TYPE=Release',
                "ppq004-build",
                ros,
                repo,
            ],
        )
    executable = native / "hope_ppq004_state_replay"
    if executable.exists():
        run("controlled-states", [native / "test_ppq004_state_contract"])
        for name, flags in [
            ("managed", []),
            ("strict", ["--profile", "strict"]),
            ("position-only", ["--position-only"]),
            ("magnus-off", ["--set", "magnus_k=0"]),
            (
                "train-free-flight",
                [
                    "--set",
                    "drag_k=0.12509060571761474",
                    "--set",
                    "magnus_k=0.004018823648810745",
                ],
            ),
            ("managed-commands", ["--command-fixtures"]),
        ]:
            run(
                name,
                [
                    py,
                    scripts / "ppq004_replay.py",
                    "--prepared",
                    root / "prepared",
                    "--executable",
                    executable,
                    "--output",
                    root / name,
                    "--plane-x",
                    config["plane_x_m"][0],
                    *flags,
                ],
                "interface_fixture"
                if name == "managed-commands"
                else "measured_recording",
                ("prepare",),
            )
        for profile in ("managed", "strict"):
            for part, frames in ((1, 65535), (2, 65535), (3, 15861)):
                run(
                    f"state-{profile}-{part}",
                    [
                        py,
                        scripts / "state_machine_scoring.py",
                        "--trace",
                        root / profile / f"ppq004_part{part}.trace.jsonl",
                        "--annotations",
                        package / "test/fixtures/ppq004/reviewed_intervals.jsonl",
                        "--frames",
                        frames,
                        "--recording-id",
                        f"ppq004_part{part}",
                        "--output",
                        root / f"state-score-{profile}-{part}.json",
                    ],
                    "measured_recording",
                    (profile,),
                )
                state_receipt = root / f"state-score-{profile}-{part}.json"
                if state_receipt.exists():
                    results["gates"][f"state-{profile}-{part}"]["status"] = json.loads(
                        state_receipt.read_text()
                    )["verdict"]
                    save()
        for profile in ("managed", "position-only", "magnus-off", "train-free-flight"):
            for split in ("development", "benchmark_holdout"):
                run(
                    f"forecast-{profile}-{split}",
                    [
                        py,
                        scripts / "ppq004_forecast_score.py",
                        "--source",
                        root / "source",
                        "--replay",
                        root / profile,
                        "--annotations",
                        root / "annotations/episodes.jsonl",
                        "--split",
                        split,
                        "--output",
                        root / f"forecast-{profile}-{split}",
                    ],
                    "measured_recording",
                    (profile, "annotations"),
                )
        run(
            "public-plane-comparison",
            [
                py,
                scripts / "ppq004_plane_comparison.py",
                "--source",
                root / "source",
                "--annotations",
                root / "annotations/episodes.jsonl",
                "--v2-executable",
                native / "hope_flight_prediction_v2_replay",
                "--baseline-executable",
                native / "hope_ball_flight_baseline_replay",
                "--output",
                root / "public-plane-comparison",
            ],
            "measured_recording",
            ("annotations",),
        )
        run(
            "paired-forecasts",
            [
                py,
                scripts / "ppq004_paired_forecasts.py",
                root,
                "--output",
                root / "paired-forecasts",
            ],
            "measured_recording",
        )
        run(
            "conversion",
            [
                py,
                scripts / "incoming_conversion_simulation.py",
                "--probe",
                native / "hope_incoming_conversion_probe",
                "--output",
                root / "conversion",
            ],
            "independent_simulation",
        )
        run(
            "outgoing-mujoco",
            [
                py,
                scripts / "mujoco_conversion_replay.py",
                "--repo",
                repo,
                "--conversion",
                root / "conversion",
                "--output",
                root / "outgoing-mujoco",
            ],
            "independent_simulation",
            ("conversion",),
        )
    else:
        results["gates"]["native-recorded"] = dict(
            status="NOT_RUN", reason="Native replay executable unavailable"
        )
    if (ros / "install/setup.bash").exists():

        def ros_trial(name, rate, mode, part=3, fault="none", seconds=None):
            command = [
                py,
                package / "test/v2_incoming_producer_chain.py",
                "--repo",
                repo,
                "--build",
                ros / "build/hope_planner_cpp",
                "--bringup",
                ros / "install/hope_bringup/lib/hope_bringup",
                "--output",
                root / name,
                "--rate",
                rate,
                "--mode",
                mode,
                "--spin",
                "zero",
                "--recorded-observations",
                root / "prepared/observations.jsonl",
                "--recording-id",
                f"ppq004_part{part}",
                "--recorded-fault",
                fault,
            ]
            if seconds:
                command += ["--recorded-max-seconds", seconds]
            run(
                name,
                [
                    "bash",
                    "-c",
                    'source "$1"; shift; export ROS_DOMAIN_ID=194 ROS_LOCALHOST_ONLY=1 RMW_IMPLEMENTATION=rmw_fastrtps_cpp; exec "$@"',
                    "ppq004-ros",
                    ros / "install/setup.bash",
                    *command,
                ],
                "measured_recording" if fault == "none" else "controlled_modification",
                ("prepare",),
            )

        for repetition in range(1 if a.development else config["repetitions"]):
            for rate in [300] if a.development else config["nominal_ros_hz"]:
                for mode in ["fixed"] if a.development else config["plane_modes"]:
                    ros_trial(
                        f"ros-{repetition + 1}-{rate}-{mode}",
                        rate,
                        mode,
                        seconds=25 if a.development else None,
                    )
        if not a.development:
            for part in (1, 2):
                ros_trial(f"ros-full-take-{part}", 300, "fixed", part=part)
            for fault in (
                "missing_orientation",
                "quaternion_sign",
                "short_gap",
                "source_gap",
                "long_gap",
                "spike",
                "duplicate",
                "reordered",
                "clock_backstep",
                "wrong_frame",
                "wrong_calibration",
                "typed_loss",
                "typed_delay",
                "worker_stall",
                "decoder_delay",
                "home_change",
                "source_silence",
            ):
                ros_trial("ros-fault-" + fault, 300, "fixed", fault=fault, seconds=25)
    else:
        results["gates"]["ros-recorded"] = dict(
            status="NOT_RUN", reason="ROS installation unavailable"
        )
    if os.environ.get("ORT_ROOT"):
        run(
            "runner-baseline-source",
            [
                "git",
                "worktree",
                "add",
                "--detach",
                root / "runner-baseline-source",
                "4d2247c69100f1e5416a8f42468b4d67418c45fb",
            ],
        )
        run(
            "runner-lifecycle",
            [
                "bash",
                scripts / "verify_runner_revocation.sh",
                root / "runner-lifecycle",
                root / "runner-baseline-source",
            ],
            requires=("runner-baseline-source",),
        )
        run(
            "policy-bridge",
            ["bash", scripts / "build_ppq004_policy_bridge.sh", root / "policy-bridge"],
        )
        run(
            "coupled-scenarios",
            [
                py,
                scripts / "ppq004_scenarios.py",
                "--native",
                executable,
                "--source",
                root / "source",
                "--replay",
                root / "managed-commands",
                "--output",
                root / "coupled-scenarios",
            ],
            "measured_recording",
            ("managed-commands",),
        )
        if (root / "coupled-scenarios/manifest.json").exists():
            for name, gate in (
                json.loads((root / "coupled-scenarios/manifest.json").read_text())
                .get("extensions", {})
                .items()
            ):
                results["gates"]["coupled-source-" + name] = dict(
                    gate, evidence_type="independent_simulation"
                )
            save()
            for scenario in sorted(
                (root / "coupled-scenarios").glob("scenario-*.json")
            ):
                run(
                    "coupled-" + scenario.stem,
                    [
                        py,
                        scripts / "ppq004_coupled_simulation.py",
                        "--repo",
                        repo,
                        "--library",
                        root / "policy-bridge/libppq004_policy.so",
                        "--scenario",
                        scenario,
                        "--output",
                        root / ("coupled-" + scenario.stem),
                    ],
                    "independent_simulation",
                    ("policy-bridge",),
                )
    else:
        results["gates"]["runner-lifecycle"] = dict(
            status="NOT_RUN", reason="ORT_ROOT not supplied"
        )
        results["gates"]["coupled-execution"] = dict(
            status="NOT_RUN", reason="Production policy bridge unavailable"
        )
    if not any(name.startswith("coupled-scenario-") for name in results["gates"]):
        results["gates"].setdefault(
            "coupled-execution",
            dict(status="NOT_COVERED", reason="No executable decoded scenario"),
        )
    results["gates"]["physical-qualification"] = dict(
        status="NOT_RUN",
        evidence_type="physical_capture",
        reason="Authorized scope is protocols only",
    )
    results["gates"]["independent-five-state-holdout"] = dict(
        status="NOT_COVERED",
        evidence_type="measured_recording",
        reason="No outgoing serve holdout or fresh independent session; synthetic coverage is separate",
    )
    results["gates"]["historical-loss-closure"] = dict(
        status="FAIL",
        reason="Seven historical and one fresh retained lost-flight cases are not repaired by this validation campaign",
    )
    results["gates"]["complete-command-opportunities"] = dict(
        status="INCONCLUSIVE",
        reason="Recorded physical boundaries/eligibility are not fully annotated; native fixture success cannot qualify ROS delivery",
    )
    run("plots", [py, scripts / "ppq004_plots.py", root], "measured_recording")
    results["status"] = (
        "INCOMPLETE"
        if any(g["status"] != "PASS" for g in results["gates"].values())
        else "PASS"
    )
    results["requirements"] = requirement_results(
        results["gates"],
        json.loads((package / "docs/ppq004_requirements.json").read_text())[
            "requirements"
        ],
    )
    results["completed_ns"] = time.time_ns()
    save()
    report(root)
    return 0 if results["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
