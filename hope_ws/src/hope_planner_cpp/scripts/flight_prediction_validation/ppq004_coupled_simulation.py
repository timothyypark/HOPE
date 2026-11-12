"""Production policy + dynamic robot/ball simulation, separate from ball-only replay.

No joint pinning after initialization and no forced racket collision. The input
scenario must contain an actual decoded wire target and a causal initial ball
state. A miss or fall is retained as FAIL, never repaired by teleporting the ball.
"""

import argparse
import ctypes
import json
from pathlib import Path
import sys
import time
import numpy as np
from ppq004_dataset import sha256


def outgoing_crossing(before, after, net_x, net_height, radius):
    """Require a forward net-plane crossing, then report ball-surface clearance."""
    if not before[0] < net_x <= after[0]:
        return None
    fraction = (net_x - before[0]) / (after[0] - before[0])
    point = np.asarray(before) + fraction * (np.asarray(after) - before)
    return dict(
        position_table=point.tolist(), clearance_m=float(point[2] - radius - net_height)
    )


def engaged_identity(level, lifecycle, expected):
    """Credit only the command that owns the active frozen policy swing."""
    return (
        level == 1
        and expected is not None
        and tuple(map(int, lifecycle[:2])) == expected
    )


def simulate(repo, library, scenario, output):
    import mujoco

    output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(repo / "apps/a3_mujoco_serve"))
    from a3_serve.mujoco_scene import A3ServeScene

    cfg_path = repo / "apps/a3_mujoco_serve/config/serve.json"
    cfg = json.loads(cfg_path.read_text())
    cfg["physics"]["drag"]["k"] = scenario["drag_k"]
    scene = A3ServeScene(
        (cfg_path.parent / cfg["model"]["xml"]).resolve(), cfg["physics"], cfg["model"]
    )
    lib = ctypes.CDLL(str(library.resolve()))
    vec = np.ctypeslib.ndpointer(dtype=np.float64, flags="C_CONTIGUOUS")
    lib.ppq_create.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    lib.ppq_create.restype = ctypes.c_void_p
    lib.ppq_destroy.argtypes = [ctypes.c_void_p]
    lib.ppq_stand.argtypes = [ctypes.c_void_p, vec]
    lib.ppq_delivered.argtypes = [ctypes.c_void_p]
    lib.ppq_home.argtypes = [ctypes.c_void_p]
    lib.ppq_home.restype = ctypes.c_ulonglong
    lib.ppq_status.argtypes = [ctypes.c_void_p]
    lib.ppq_status.restype = ctypes.c_char_p
    lib.ppq_wire.argtypes = [ctypes.c_void_p, vec, ctypes.c_int]
    lib.ppq_wire.restype = ctypes.c_int
    lib.ppq_step.argtypes = [ctypes.c_void_p, vec, vec]
    lib.ppq_step.restype = ctypes.c_int
    ids = np.ctypeslib.ndpointer(dtype=np.uint64, flags="C_CONTIGUOUS")
    lib.ppq_lifecycle.argtypes = [ctypes.c_void_p, ids]
    lib.ppq_geometry.argtypes = [ctypes.c_void_p, vec]
    lib.ppq_lifecycle.restype = None
    lib.ppq_geometry.restype = None
    lifecycle = np.zeros(8, dtype=np.uint64)
    geometry = np.zeros(16)
    expected_identity = None
    policies = repo / "hope_training/whole_body_tracking/checkpoints"
    p = lib.ppq_create(
        str(policies / "policy.onnx").encode(), str(policies / "deploy.yaml").encode()
    )
    if not p:
        raise RuntimeError("production policy initialization failed")
    stand = np.empty(93)
    lib.ppq_stand(p, stand)
    scene.reset(stand[:31])
    m, d = scene.model, scene.data
    qa = scene.qpos_addresses
    va = scene.dof_addresses
    # Table -> simulator translation; policy Z uses table Z + 0.76 once.
    policy_shift = scene.offset - np.array([0.0, 0.0, 0.76])
    root = scene.base_qpos_address
    rv = scene.base_dof_address
    d.qpos[root : root + 2] = (
        np.array(scenario.get("base_xy", [-0.5, -0.7625])) + scene.offset[:2]
    )
    yaw = float(scenario.get("base_yaw_rad", 0))
    d.qpos[root + 3 : root + 7] = [np.cos(yaw / 2), 0, 0, np.sin(yaw / 2)]
    d.qvel[rv : rv + 2] = scenario.get("base_velocity_xy", [0.0, 0.0])
    mujoco.mj_forward(m, d)
    actuators = []
    for joint in scene.joint_ids:
        hits = np.flatnonzero(m.actuator_trnid[:, 0] == joint)
        if len(hits) != 1:
            raise ValueError("joint actuator mapping must be one-to-one")
        actuators.append(int(hits[0]))
    actuators = np.array(actuators)
    command = np.zeros(155)
    command[:31] = stand[:31]
    command[93:124] = stand[31:62]
    command[124:155] = stand[62:]
    start = time.monotonic()
    contacts = []
    rows = []
    engaged_attempts = set()
    decoded_attempts = set()
    launched = False
    landings = {}
    net_contacts = set()
    outgoing_crossings = {}
    max_tilt = 0.0
    max_lateness = 0.0
    launch_ticks = [25 + 125 * i for i in range(int(scenario.get("repetitions", 1)))]
    attempt = -1
    recovery = []
    duration = float(scenario.get("duration_s", 2.5))
    steps = max(1, round(0.02 / m.opt.timestep))
    try:
        for tick in range(int(duration / 0.02)):
            wait = start + tick * 0.02 - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            max_lateness = max(max_lateness, time.monotonic() - (start + tick * 0.02))
            if tick in launch_ticks:
                attempt += 1
                if attempt:
                    recovery.append(
                        bool(
                            rows
                            and rows[-1]["level"] == 0
                            and rows[-1]["tilt_deg"] < 30
                        )
                    )
                if not lib.ppq_home(p):
                    raise RuntimeError("no production HOME before target")
                wire = np.array(scenario["wire"], dtype=np.float64)
                now = time.time()
                lead = float(scenario["contact_lead_s"])
                wire[9] = lead
                wire[10] = now + lead
                wire[12] = int(now)
                wire[13] = int((now - int(now)) * 1e9)
                wire[19] = lib.ppq_home(p)
                wire[14] += attempt
                wire[15] += 1000 * attempt
                expected_identity = (int(wire[14]), int(wire[15]))
                if lib.ppq_wire(p, wire, len(wire)) == 1:
                    decoded_attempts.add(attempt)
                scene._set_ball(
                    np.asarray(scenario["ball_position_table"]) + scene.offset,
                    scenario["ball_velocity"],
                )
                d.qvel[scene.ball_dof_address + 3 : scene.ball_dof_address + 6] = (
                    scenario.get("ball_spin", [0.0, 0.0, 0.0])
                )
                launched = True
            mujoco.mj_kinematics(m, d)
            racket_before_policy = (
                d.site_xpos[scene.racket_site_id].copy() - policy_shift
            )
            ball_before_policy = (
                d.qpos[scene.ball_qpos_address : scene.ball_qpos_address + 3].copy()
                - policy_shift
            )
            state = np.concatenate(
                [
                    d.qpos[qa],
                    d.qvel[va],
                    d.qpos[root + 3 : root + 7],
                    d.qvel[rv + 3 : rv + 6],
                    d.qpos[root : root + 3] - policy_shift,
                    d.xquat[m.body("torso_Link").id],
                ]
            )
            level = lib.ppq_step(p, np.ascontiguousarray(state), command)
            if level < 0:
                raise RuntimeError("policy step failed")
            lib.ppq_lifecycle(p, lifecycle)
            lib.ppq_geometry(p, geometry)
            if engaged_identity(level, lifecycle, expected_identity) and attempt >= 0:
                engaged_attempts.add(attempt)
            for _ in range(steps):
                torque = (
                    command[93:124] * (command[:31] - d.qpos[qa])
                    + command[124:155] * (command[31:62] - d.qvel[va])
                    + command[62:93]
                )
                d.ctrl[actuators] = np.clip(
                    torque,
                    m.actuator_ctrlrange[actuators, 0],
                    m.actuator_ctrlrange[actuators, 1],
                )
                scene._apply_drag()
                if scenario.get("magnus_k", 0):
                    spatial = np.zeros(6)
                    mujoco.mj_objectVelocity(
                        m, d, mujoco.mjtObj.mjOBJ_BODY, scene.ball_body_id, spatial, 0
                    )
                    d.xfrc_applied[scene.ball_body_id, :3] += (
                        scene.ball_mass
                        * scenario["magnus_k"]
                        * np.cross(spatial[:3], spatial[3:])
                    )
                before_ball = (
                    d.qpos[scene.ball_qpos_address : scene.ball_qpos_address + 3].copy()
                    - scene.offset
                )
                mujoco.mj_step(m, d)
                after_ball = (
                    d.qpos[scene.ball_qpos_address : scene.ball_qpos_address + 3]
                    - scene.offset
                )
                if (
                    any(c["attempt"] == attempt for c in contacts)
                    and attempt not in outgoing_crossings
                ):
                    crossing = outgoing_crossing(
                        before_ball,
                        after_ball,
                        scene.net_x_table,
                        scene.net_height,
                        scene.ball_radius,
                    )
                    if crossing is not None:
                        outgoing_crossings[attempt] = crossing
                if launched:
                    for c in range(d.ncon):
                        contact = d.contact[c]
                        geoms = {contact.geom1, contact.geom2}
                        if scene.ball_geom_id not in geoms:
                            continue
                        force = np.zeros(6)
                        mujoco.mj_contactForce(m, d, c, force)
                        impulse = float(np.linalg.norm(force[:3]) * m.opt.timestep)
                        if scene.racket_geom_id in geoms and impulse > 1e-8:
                            contacts.append(
                                dict(
                                    attempt=attempt,
                                    time_s=float(d.time),
                                    impulse_ns=impulse,
                                    position=d.qpos[
                                        scene.ball_qpos_address : scene.ball_qpos_address
                                        + 3
                                    ].tolist(),
                                )
                            )
                        if scene.net_geom_id in geoms:
                            net_contacts.add(attempt)
                        if (
                            any(c["attempt"] == attempt for c in contacts)
                            and scene.table_geom_id in geoms
                            and attempt not in landings
                        ):
                            landings[attempt] = (
                                d.qpos[
                                    scene.ball_qpos_address : scene.ball_qpos_address
                                    + 3
                                ]
                                - scene.offset
                            ).tolist()
            lib.ppq_delivered(p)
            quat = d.qpos[root + 3 : root + 7]
            up = 1 - 2 * (quat[1] ** 2 + quat[2] ** 2)
            tilt = float(np.degrees(np.arccos(np.clip(up, -1, 1))))
            max_tilt = max(max_tilt, tilt)
            rows.append(
                dict(
                    tick=tick,
                    attempt=attempt,
                    time_since_launch_s=(tick - launch_ticks[attempt]) * 0.02
                    if attempt >= 0
                    else None,
                    time_s=float(d.time),
                    level=level,
                    policy_status=lib.ppq_status(p).decode(),
                    policy_lifecycle=lifecycle.tolist(),
                    expected_command_identity=expected_identity,
                    policy_target=geometry[1:4].tolist(),
                    policy_racket_fk=geometry[4:7].tolist() if geometry[0] else None,
                    mujoco_racket_before_policy=racket_before_policy.tolist(),
                    ball_before_policy=ball_before_policy.tolist(),
                    ball_racket_site_distance_m=float(
                        np.linalg.norm(ball_before_policy - racket_before_policy)
                    ),
                    racket_fk_residual_m=float(
                        np.linalg.norm(geometry[4:7] - racket_before_policy)
                    )
                    if geometry[0]
                    else None,
                    tilt_deg=tilt,
                    base=d.qpos[root : root + 3].tolist(),
                    ball_table=(
                        d.qpos[scene.ball_qpos_address : scene.ball_qpos_address + 3]
                        - scene.offset
                    ).tolist(),
                    q=d.qpos[qa].tolist(),
                    dq=d.qvel[va].tolist(),
                )
            )
    finally:
        lib.ppq_destroy(p)
    landing_errors = {
        i: float(np.linalg.norm(np.asarray(landing) - scenario["target_land"]))
        for i, landing in landings.items()
    }
    gates = dict(
        decoded=len(decoded_attempts) == len(launch_ticks),
        engaged=len(engaged_attempts) == len(launch_ticks),
        racket_contact=len({c["attempt"] for c in contacts}) == len(launch_ticks),
        net_clearance=len(outgoing_crossings) == len(launch_ticks)
        and not net_contacts
        and all(c["clearance_m"] > 0 for c in outgoing_crossings.values()),
        landing=len(landing_errors) == len(launch_ticks)
        and all(
            e <= scenario.get("landing_tolerance_m", 0.2)
            for e in landing_errors.values()
        ),
        balance=max_tilt < 30,
        successive_ball_recovery=bool(recovery) and all(recovery),
    )
    incoming_errors = []
    truth = scenario.get("incoming_comparison_only", {})
    if truth.get("source_ns"):
        truth_t = (
            np.asarray(truth["source_ns"], dtype=np.int64) - scenario["source_ns"]
        ) * 1e-9
        truth_p = np.asarray(truth["positions"])
        for row in rows:
            elapsed = row["time_since_launch_s"]
            if elapsed is None or not truth_t[0] <= elapsed <= truth_t[-1]:
                continue
            # Rows are observed after one policy tick's integration.
            elapsed += 0.02
            if elapsed > truth_t[-1]:
                continue
            if any(
                c["attempt"] == row["attempt"] and c["time_s"] <= row["time_s"]
                for c in contacts
            ):
                continue
            measured = [
                np.interp(elapsed, truth_t, truth_p[:, axis]) for axis in range(3)
            ]
            incoming_errors.append(
                dict(
                    attempt=row["attempt"],
                    elapsed_s=elapsed,
                    position_error_m=float(
                        np.linalg.norm(np.asarray(row["ball_table"]) - measured)
                    ),
                )
            )
    result = dict(
        incoming_recorded_proxy_comparison=incoming_errors,
        status="PASS" if all(gates.values()) else "FAIL",
        evidence_type="independent_simulation",
        parent_evidence_type=scenario["evidence_type"],
        gates=gates,
        contacts=contacts,
        landing_table=landings,
        landing_error_m=landing_errors,
        max_tilt_deg=max_tilt,
        max_wall_lateness_s=max_lateness,
        recovery_between_balls=recovery,
        outgoing_net_crossings=outgoing_crossings,
        net_contact_attempts=sorted(net_contacts),
        sampled_closest_ball_site_distance_m={
            i: min(r["ball_racket_site_distance_m"] for r in rows if r["attempt"] == i)
            for i in range(attempt + 1)
        },
        distance_sampling_scope="Same-instant 20 ms policy samples; not a contact-time or sub-step closest-distance measurement",
        first_contact_errors=[
            dict(
                attempt=i,
                ball_center_to_command_point_error_m=float(
                    np.linalg.norm(
                        np.asarray(
                            next(c for c in contacts if c["attempt"] == i)["position"]
                        )
                        - policy_shift
                        - np.asarray(scenario["wire"])[3:6]
                    )
                ),
                timing_error_s=next(c for c in contacts if c["attempt"] == i)["time_s"]
                - launch_ticks[i] * 0.02
                - scenario["contact_lead_s"],
            )
            for i in sorted({c["attempt"] for c in contacts})
        ],
        attempts=attempt + 1,
        decoded_attempts=sorted(decoded_attempts),
        engaged_attempts=sorted(engaged_attempts),
        engagement_evidence="Active frozen command sequence AND flight ID, not level alone",
        racket_control_point_scope="Policy FK versus provided MuJoCo site diagnostic; no physical registration claim",
        physical_execution="NOT_RUN",
        scenario=scenario,
        hashes={
            "bridge": sha256(library),
            "policy": sha256(policies / "policy.onnx"),
            "deploy": sha256(policies / "deploy.yaml"),
            "scene_config": sha256(cfg_path),
        },
        coordinate_transform={
            "table_to_mujoco": scene.offset.tolist(),
            "policy_to_mujoco": policy_shift.tolist(),
        },
        physics=cfg["physics"],
        mujoco_version=mujoco.__version__,
    )
    (output / "trace.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (output / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("repo", "library", "scenario", "output"):
        p.add_argument("--" + name, type=Path, required=True)
    a = p.parse_args()
    result = simulate(a.repo, a.library, json.loads(a.scenario.read_text()), a.output)
    print(json.dumps(result))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
