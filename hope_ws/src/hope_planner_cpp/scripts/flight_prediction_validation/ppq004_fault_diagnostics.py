"""Score each recorded fault's observable response, separately from transport.

Missing exposure is NOT_COVERED. These checks do not invent physical command
opportunities or substitute decoder status for policy engagement.
"""

import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import sys
import numpy as np
from ppq004_dataset import sha256

FAULTS = (
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
)


def verdict(exercised, correct, scope, **evidence):
    return dict(
        status="NOT_COVERED" if not exercised else "PASS" if correct else "FAIL",
        scope=scope,
        **evidence,
    )


def assess(raw, baseline, stages, decisions):
    source = raw["source"]
    received = raw["received"]
    fault = source["transformation"]
    offered = source["rows"]
    grouped = defaultdict(list)
    for row in stages:
        grouped[row["stage"]].append(row)
    stamps = {
        key: {int(row["source_ns"]) for row in values}
        for key, values in grouped.items()
    }
    commands = [row for row in received["commands"] if row[1] == 1]
    published = {int(row["sequence"]): row for row in grouped["command_published"]}
    fresh = all(
        0 <= int(row["wall_ns"]) - int(row["source_ns"]) <= 30000000
        for row in published.values()
    )
    anchor = next(
        (
            row["source_index"]
            for row in offered
            if row["source_index"] >= 900 and row["original_present"]
        ),
        None,
    )
    physical = [
        row for row in received["full"] if row["physical"] and row.get("trajectory")
    ]
    if fault == "missing_orientation":
        waypoints = [w for row in physical for w in row["trajectory"]]
        return verdict(
            bool(waypoints),
            not any(w["spin_available"] for w in waypoints),
            "Available physical forecasts do not manufacture available spin from orientation-free input",
            waypoints=len(waypoints),
        )
    if fault == "quaternion_sign":
        if baseline is None:
            return dict(status="NOT_RUN", reason="Missing nominal baseline")
        reference = {
            row["source_ns"] - baseline["source"]["epoch_ns"]: row
            for row in baseline["received"]["full"]
            if row["physical"] and row.get("trajectory")
        }
        errors = []
        incompatible = 0
        for row in physical:
            other = reference.get(row["source_ns"] - source["epoch_ns"])
            if other is None:
                continue
            a = row["trajectory"]
            b = other["trajectory"]
            if len(a) != len(b):
                incompatible += 1
                continue
            values = lambda points: np.asarray(
                [w["position"] + w["velocity"] + w["omega"] for w in points]
            )
            errors.append(float(np.max(np.abs(values(a) - values(b)))))
            incompatible += any(
                x["spin_available"] != y["spin_available"] for x, y in zip(a, b)
            )
        return verdict(
            bool(errors) or incompatible > 0,
            not incompatible and all(e <= 1e-8 for e in errors),
            "Actual full forecasts at common source cutoffs under quaternion sign reversal; conditional on paired availability",
            paired_cutoffs=len(errors),
            incompatible_pairs=incompatible,
            maximum_component_error=max(errors, default=None),
            equality_tolerance=1e-8,
        )
    if fault in ("short_gap", "source_gap", "long_gap", "source_silence"):
        absent = {
            row["source_ns"]
            for row in offered
            if row["original_present"] and not row["present"]
        }
        fabricated = absent & stamps.get("planner_received", set())
        response = verdict(
            bool(absent),
            not fabricated and fresh,
            "Injected missing Ball frames remain absent downstream; publication freshness remains separate from physical recovery coverage",
            injected_absent_frames=len(absent),
            fabricated_measurements=sorted(fabricated),
        )
        response["expiry_events_observed"] = sum(
            row["phase"] == "after_expire" and row["source_fault"] == "1"
            for row in decisions
        )
        response["physical_recovery_opportunities"] = (
            "INCONCLUSIVE: no qualified physical flight denominator"
        )
        return response
    if fault in ("spike", "wrong_frame"):
        stop = (
            anchor + (30 if fault == "wrong_frame" else 1) if anchor is not None else 0
        )
        bad = {
            row["source_ns"]
            for row in offered
            if row["present"]
            and anchor is not None
            and anchor <= row["source_index"] < stop
        }
        delivered = bad & stamps.get("planner_received", set())
        rejected = delivered & stamps.get("tracker_rejected", set())
        accepted = delivered & stamps.get("tracker_accepted", set())
        return verdict(
            bool(delivered),
            delivered == rejected and not accepted and fresh,
            "Injected bad observations delivered to the owner are rejected rather than accepted",
            delivered_bad=len(delivered),
            rejected_bad=len(rejected),
            accepted_bad=len(accepted),
        )
    if fault == "wrong_calibration":
        return verdict(
            bool(grouped["planner_received"]),
            not grouped["tracker_accepted"] and not commands,
            "Wrong-calibration observations reach the owner and cannot qualify tracking or commands",
            delivered=len(grouped["planner_received"]),
        )
    if fault == "duplicate":
        duplicate_stamps = {
            stamp
            for stamp, count in Counter(
                row["source_ns"] for row in offered if row["present"]
            ).items()
            if count > 1
        }
        accepted = Counter(int(row["source_ns"]) for row in grouped["tracker_accepted"])
        rejected = stamps.get("tracker_rejected", set())
        return verdict(
            bool(duplicate_stamps),
            all(accepted[s] <= 1 and s in rejected for s in duplicate_stamps),
            "An actually duplicated Ball timestamp is accepted at most once and the duplicate is rejected",
            duplicated_ball_timestamps=sorted(duplicate_stamps),
        )
    if fault in ("clock_backstep", "reordered"):
        indices = (
            {anchor}
            if fault == "clock_backstep"
            else {anchor, None if anchor is None else anchor + 1}
        )
        altered = {
            row["source_ns"]
            for row in offered
            if row["source_index"] in indices and row["present"]
        }
        rejection = [
            row
            for row in grouped["tracker_rejected"]
            if int(row["source_ns"]) in altered
        ]
        if fault == "clock_backstep":
            rejection = [
                row
                for row in rejection
                if int(row["wall_ns"]) - int(row["source_ns"]) > 30000000
            ]
        return verdict(
            bool(altered & stamps.get("planner_received", set())),
            bool(rejection) and fresh,
            "Altered source clock/order reaches the owner and produces rejection; no stale publication is permitted",
            rejected_altered=len(rejection),
        )
    if fault == "typed_loss":
        dropped = stamps.get("typed_intentionally_dropped", set())
        return verdict(
            bool(dropped),
            dropped <= stamps.get("relay_receipt", set())
            and not dropped & stamps.get("typed_published", set())
            and not dropped & stamps.get("planner_received", set()),
            "Explicit relay drops are absent at both downstream boundaries",
            dropped=len(dropped),
        )
    if fault == "typed_delay":
        rows = grouped["planner_received"]
        return verdict(
            bool(rows),
            not commands
            and not grouped["tracker_accepted"]
            and all(int(r["wall_ns"]) - int(r["source_ns"]) > 30000000 for r in rows),
            "Actually delayed observations exceed source freshness and cannot qualify tracking or new commands",
            delivered=len(rows),
        )
    if fault == "home_change":
        new = [row for row in received["candidates"] if row["home"] == 101]
        first = min((row["published_ns"] for row in new), default=None)
        stale = [
            wire
            for wire in commands
            if int(wire[14]) in published
            and first is not None
            and int(published[int(wire[14])]["wall_ns"]) >= first
            and wire[19] != 101
        ]
        return verdict(
            bool(new),
            not stale and fresh,
            "The new HOME is advertised and subsequent commands do not carry the retired HOME",
            new_home_candidates=len(new),
            stale_home_commands=len(stale),
        )
    if fault == "decoder_delay":
        delayed = []
        wires = {int(wire[14]): wire for wire in commands}
        for row in received["decoded"]:
            seq = int(row[0])
            if row[10] or seq not in published or seq not in wires:
                continue
            receipt = int(row[13]) * 10**9 + int(row[14])
            age = receipt - int(published[seq]["wall_ns"])
            if age > 10000000:
                delayed.append(
                    dict(
                        sequence=seq,
                        transport_delay_ms=age * 1e-6,
                        remaining_deadline_s=wires[seq][10] - receipt * 1e-9,
                        reported_tts_s=row[9],
                    )
                )
        return verdict(
            bool(delayed),
            all(
                abs(r["remaining_deadline_s"] - r["reported_tts_s"]) <= 0.01
                for r in delayed
            ),
            "Delayed actual decoder receipts preserve the absolute deadline; no policy-engagement claim",
            delayed_targets=delayed,
            timing_tolerance_s=0.01,
        )
    if fault == "worker_stall":
        late = [
            row
            for row in grouped["forecast_completed"]
            if int(row.get("duration_ns", 0)) > 30000000
        ]
        return verdict(
            bool(late),
            fresh,
            "An actually delayed forecast completes while new command publications remain source-fresh",
            delayed_completions=len(late),
            stall_receipts=raw.get("fault_injections", []),
        )
    raise ValueError("Unknown recorded fault: " + fault)


def run(root, output):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "test"))
    from qualification_accounting import read_stages

    output.mkdir(parents=True, exist_ok=False)
    reference = root / "ros-1-300-fixed/raw.json"
    baseline = json.loads(reference.read_text()) if reference.exists() else None
    rows = {}
    for fault in FAULTS:
        directory = root / ("ros-fault-" + fault)
        raw_path = directory / "raw.json"
        if not raw_path.exists():
            rows[fault] = dict(status="NOT_RUN", reason="Missing invocation")
            continue
        original_path = directory / "result.json"
        if not original_path.exists():
            rows[fault] = dict(
                status="INCONCLUSIVE", reason="Invocation has no final result"
            )
            continue
        original = json.loads(original_path.read_text())
        if not all(
            original.get("observer", {}).get(name) == "PASS"
            for name in ("relay.tsv", "planner.tsv", "decoder.tsv", "decisions.tsv")
        ):
            rows[fault] = dict(
                status="INCONCLUSIVE",
                reason="Incomplete original trace evidence",
                original_result_sha256=sha256(original_path),
            )
            continue
        raw = json.loads(raw_path.read_text())
        stages = []
        hashes = {"raw": sha256(raw_path)}
        if raw.get("exception") or not raw.get("source", {}).get("complete"):
            rows[fault] = dict(
                status="INCONCLUSIVE",
                reason="Source invocation did not complete",
                input_sha256=hashes,
            )
            continue
        for name in ("relay.tsv", "planner.tsv", "decoder.tsv"):
            metadata, records = read_stages(directory / name)
            if int(metadata.get("overwritten", -1)) != 0:
                raise ValueError("Incomplete stage evidence: " + str(directory / name))
            stages.extend(records)
            hashes[name] = sha256(directory / name)
        with (directory / "decisions.tsv").open() as stream:
            decisions = list(
                csv.DictReader(
                    (line for line in stream if not line.startswith("#")),
                    delimiter="\t",
                )
            )
        hashes["decisions.tsv"] = sha256(directory / "decisions.tsv")
        rows[fault] = dict(
            assess(raw, baseline, stages, decisions), input_sha256=hashes
        )
    status = (
        "NOT_RUN"
        if all(row["status"] == "NOT_RUN" for row in rows.values())
        else "FAIL"
        if any(row["status"] == "FAIL" for row in rows.values())
        else "INCONCLUSIVE"
        if any(row["status"] != "PASS" for row in rows.values())
        else "PASS"
    )
    result = dict(
        status=status,
        evidence_type="controlled_modification",
        faults=rows,
        baseline_sha256=sha256(reference) if reference.exists() else None,
        consumer_engagement="NOT_COVERED: actual Runner fixtures remain separate",
    )
    (output / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.root, args.output)
    print(json.dumps({name: row["status"] for name, row in result["faults"].items()}))
    raise SystemExit(int(result["status"] == "FAIL"))
