"""Recorded camera source for the unchanged production-chain harness.

Only the camera path is measured. HOME and robot base are explicit fixtures;
raw base/paddle markers are preserved in the prepared dataset, not promoted to
registered robot control points. Original source intervals are never resampled.
"""

import json
import time
from pathlib import Path
import rclpy
from rclpy.qos import qos_profile_sensor_data
from motion_capture_tracking_interfaces.msg import LatencyInfo, NamedPose, NamedPoseArrayV2
from std_msgs.msg import Float64MultiArray


def recorded_source(rate, spin, stop, ready, reference_ready, queue, options):
    rclpy.init()
    node = rclpy.create_node("ppq004_recorded_camera")
    camera = node.create_publisher(NamedPoseArrayV2, "/optitrack/poses", qos_profile_sensor_data)
    home = node.create_publisher(Float64MultiArray, "/test/incoming/home", 10)
    selected = []
    with Path(options["observations"]).open() as f:
        for line in f:
            row = json.loads(line)
            if (
                row["recording_id"] == options["recording_id"]
                and row["source_index"] % (300 // rate) == 0
            ):
                selected.append(row)
    if not selected or rate not in (150, 300):
        raise ValueError("recorded source requires 150/300 Hz frames")
    if options.get("max_seconds"):
        selected = [
            r
            for r in selected
            if r["source_time_ns"] - selected[0]["source_time_ns"]
            <= int(options["max_seconds"] * 1e9)
        ]

    def message(stamp):
        m = NamedPoseArrayV2()
        m.header.stamp.sec, m.header.stamp.nanosec = divmod(stamp, 10**9)
        m.header.frame_id = "world"
        latency = LatencyInfo()
        latency.source = "NatNetClockUncertainty"
        latency.latency = 20
        m.latencies.append(latency)
        body = NamedPose()
        body.name = "UCB_P1"
        body.pose.position.x = -0.5
        body.pose.position.y = -0.7625
        body.pose.orientation.w = 1.0
        m.poses.append(body)
        return m

    sequence = 0
    home_epoch = 100.0

    def publish_home():
        nonlocal sequence
        sequence += 1
        m = Float64MultiArray()
        m.data = [
            2.0,
            home_epoch,
            -0.5,
            -0.7625,
            0.58,
            float(int("b" * 13, 16)),
            float(int("a" * 13, 16)),
            5.0,
            float(sequence),
            1.0,
        ]
        home.publish(m)

    deadline = time.monotonic() + 12
    while not reference_ready.is_set() and time.monotonic() < deadline:
        camera.publish(message(time.time_ns()))
        publish_home()
        rclpy.spin_once(node, timeout_sec=0.01)
    if not reference_ready.is_set():
        raise RuntimeError("HOME fixture not ready")
    epoch = time.time_ns() - selected[0]["source_time_ns"]
    start = time.monotonic_ns()
    first = selected[0]["source_time_ns"]
    rows = []
    ready.set()
    next_home = 0
    anchor = next(
        (
            r["source_index"]
            for r in selected
            if r["source_index"] >= 900 and r["streams"]["ball"]["available"]
        ),
        900,
    )
    for r in selected:
        if stop.is_set():
            break
        due = start + r["source_time_ns"] - first
        wait = (due - time.monotonic_ns()) * 1e-9
        if wait > 0:
            time.sleep(wait)
        stamp = epoch + r["source_time_ns"]
        m = message(stamp)
        ball = r["streams"]["ball"]
        fault = options.get("fault", "none")
        i = r["source_index"]
        present = ball["available"]
        if fault == "source_gap" and anchor <= i < anchor + 15:
            present = False
        if present:
            pose = NamedPose()
            pose.name = "Ball"
            pose.pose.position.x, pose.pose.position.y, pose.pose.position.z = ball["position_m"]
            if fault == "spike" and i == anchor:
                pose.pose.position.z += 0.5
            if (
                spin != "unknown"
                and ball["orientation_available"]
                and fault != "missing_orientation"
            ):
                q = ball["quaternion_xyzw"]
                sign = -1 if fault == "quaternion_sign" and i % 2 else 1
                (
                    pose.pose.orientation.x,
                    pose.pose.orientation.y,
                    pose.pose.orientation.z,
                    pose.pose.orientation.w,
                ) = [sign * v for v in q]
            m.poses.append(pose)
        if fault == "duplicate" and i == anchor and rows:
            stamp = rows[-1]["source_ns"]
            m.header.stamp.sec, m.header.stamp.nanosec = divmod(stamp, 10**9)
        if fault == "clock_backstep" and i == anchor:
            stamp -= 100000000
            m.header.stamp.sec, m.header.stamp.nanosec = divmod(stamp, 10**9)
        if fault == "wrong_frame" and anchor <= i < anchor + 30:
            m.header.frame_id = "unregistered"
        if fault == "home_change" and i >= anchor:
            home_epoch = 101.0
        if fault == "source_silence" and i >= anchor:
            m.poses = [pose for pose in m.poses if pose.name != "Ball"]
            present = False
        camera.publish(m)
        if time.monotonic_ns() >= next_home:
            publish_home()
            next_home = time.monotonic_ns() + 20000000
        rows.append(
            dict(
                source_ns=stamp,
                original_source_ns=r["source_time_ns"],
                source_index=i,
                source_frame_sha256=r["source_frame_sha256"],
                offered_ns=time.time_ns(),
                intended_steady_ns=due,
                present=present,
                physical_flight_id=None,
                command_opportunity="UNANNOTATED",
                parent_sha256=r["parent_sha256"],
            )
        )
    # Advance source silence long enough to expose expiry before shutdown.
    deadline = time.monotonic() + 0.15
    while time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.01)
    queue.put(
        dict(
            rows=rows,
            epoch_ns=epoch,
            rate_hz=rate,
            frames_expected=len(selected),
            complete=len(rows) == len(selected),
            base_authority="interface_fixture",
            evidence_type="measured_recording"
            if options.get("fault", "none") == "none"
            else "controlled_modification",
            transformation=options.get("fault", "none"),
            recording_id=options["recording_id"],
        )
    )
    node.destroy_node()
    rclpy.shutdown()


def recorded_result(raw, output):
    from qualification_accounting import read_stages

    offered = raw["source"].get("rows", [])
    by_stage = {}
    observer = {}
    for filename in ("relay.tsv", "planner.tsv", "decoder.tsv"):
        path = output / filename
        if not path.exists():
            observer[filename] = "NOT_RUN"
            continue
        try:
            metadata, rows = read_stages(path)
            if "missing" in metadata or "error" in metadata or int(metadata.get("overwritten", 0)):
                raise ValueError("missing or overwritten stage evidence: " + str(metadata))
            for row in rows:
                by_stage.setdefault(row["stage"], set()).add(int(row["source_ns"]))
            observer[filename] = "PASS"
        except (ValueError, AssertionError, RuntimeError) as error:
            observer[filename] = str(error)
    ball = {r["source_ns"] for r in offered if r["present"]}
    losses = {
        stage: len(ball - values)
        for stage, values in by_stage.items()
        if stage in ("relay_receipt", "typed_published", "planner_received", "tracker_accepted")
    }
    received = raw["received"]
    commands = [r for r in received["commands"] if r[1] == 1.0]
    complete = raw["source"].get("complete", False) and all(v == "PASS" for v in observer.values())
    result = dict(
        status="FAIL" if raw["exception"] else "PASS" if complete else "INCONCLUSIVE",
        scope="recorded transport and observation receipt; command opportunity eligibility requires independent annotations",
        evidence_type=raw["source"].get("evidence_type"),
        frame_count=len(offered),
        ball_frames=len(ball),
        loss_by_boundary=losses,
        observer=observer,
        valid_commands=len(commands),
        decoded=len(received["decoded"]),
        revocations=len(received["revocations"]),
        command_correctness="INCONCLUSIVE",
        measured_base_authority="NOT_COVERED",
        physical_execution="NOT_RUN",
        exception=raw["exception"],
    )
    (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
    return 0 if result["status"] == "PASS" else 1
