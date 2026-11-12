"""Source-causal event/state diagnostics from immutable native replay receipts.

Position-screened contacts are incomplete same-sensor proxy truth. Unmatched
events are not automatically false positives; unknown boundaries cannot prove
generation correctness. This scorer never supplies events to the predictor.
"""

import argparse
from collections import Counter
import json
from pathlib import Path
from ppq004_dataset import sha256


def diagnose(rows, annotations, contacts):
    events = {}
    violations = {}
    counts = Counter()
    annotation_rows = [[] for _ in annotations]
    gaps = []
    gap = None
    last_gap = None
    for row in rows:
        if "source_ns" not in row:
            continue
        now = row["source_ns"]
        for event in row.get("events", []):
            if event["status"] != 1:  # EventStatus::CONFIRMED, pinned by source SHA.
                continue
            identity = (event["generation"], event["id"])
            for name, invalid in (
                ("wrong_generation", event["generation"] != row["generation"]),
                ("future_confirmation", event["available_ns"] > now),
                ("future_occurrence", event["occurrence_ns"] > now),
            ):
                if invalid:
                    violations.setdefault((name, *identity), dict(kind=name, row=row))
            events.setdefault(
                identity,
                dict(event, first_seen_ns=now, source_index=row["source_index"]),
            )
        if row.get("phase") != "after":
            continue
        counts["frames"] += 1
        counts["present"] += bool(row["present"])
        counts["accepted"] += bool(row["accepted"])
        counts["spin_available"] += bool(row["spin_available"])
        counts["spin_available_present"] += bool(
            row["spin_available"] and row["present"]
        )
        if not row["present"]:
            if gap is None:
                gap = dict(
                    first_missing_ns=now,
                    first_source_index=row["source_index"],
                    missing_frames=0,
                )
            gap["missing_frames"] += 1
            gap["last_missing_ns"] = now
        elif gap is not None:
            gap.update(
                first_return_ns=now,
                spin_available_on_return=row["spin_available"],
                first_spin_available_after_ns=None,
            )
            gaps.append(gap)
            last_gap = gap
            gap = None
        if row["present"] and row["spin_available"] and last_gap is not None:
            if last_gap["first_spin_available_after_ns"] is None:
                last_gap["first_spin_available_after_ns"] = now
        for annotation, observed in zip(annotations, annotation_rows):
            if annotation["begin_ns"] <= now <= annotation["end_ns"]:
                observed.append(
                    dict(
                        source_ns=now,
                        state=row["play_state"],
                        generation=row["generation"],
                    )
                )
    if gap is not None:
        gaps.append(dict(gap, first_return_ns=None))
    reviewed = []
    for annotation, observed in zip(annotations, annotation_rows):
        expected = annotation["expected_state"]
        available = annotation["available_ns"]
        usable = [r for r in observed if r["source_ns"] >= available]
        correct = [r for r in usable if r["state"] == expected]
        reviewed.append(
            dict(
                annotation=annotation,
                status="INCONCLUSIVE"
                if annotation["review_status"] != "REVIEWED"
                else "NOT_COVERED"
                if not usable
                else "PASS"
                if len(correct) == len(usable)
                else "FAIL",
                causally_scored_frames=len(usable) if expected else 0,
                first_correct_source_ns=correct[0]["source_ns"] if correct else None,
                confirmation_delay_after_availability_ms=(
                    correct[0]["source_ns"] - available
                )
                * 1e-6
                if correct
                else None,
                observed_generations=sorted({r["generation"] for r in observed}),
                observed_states_after_availability=dict(
                    Counter(r["state"] for r in usable)
                ),
                physical_boundary_qualification="INCONCLUSIVE",
            )
        )
    matches = []
    table_events = [
        event for event in events.values() if event["kind"] == "table_bounce"
    ]
    matched = set()
    for contact in contacts:
        lo, hi = contact["occurrence_interval_ns"]
        candidates = [
            event for event in table_events if lo <= event["occurrence_ns"] <= hi
        ]
        for event in candidates:
            matched.add((event["generation"], event["id"]))
        matches.append(
            dict(
                contact=contact,
                status="MATCHED_PROXY"
                if len(candidates) == 1
                else "UNMATCHED_PROXY"
                if not candidates
                else "AMBIGUOUS_MULTIPLE_EVENTS",
                candidate_events=candidates,
                confirmation_delay_from_occurrence_interval_ms=[
                    [
                        (event["available_ns"] - hi) * 1e-6,
                        (event["available_ns"] - lo) * 1e-6,
                    ]
                    for event in candidates
                ],
                occurrence_error_to_proxy_estimate_ms=[
                    (event["occurrence_ns"] - contact["occurrence_estimate_ns"]) * 1e-6
                    for event in candidates
                ],
                association_scope="Conditional on a unique time-bracket match; unmatched events retained separately",
            )
        )
    return dict(
        status="FAIL" if violations else "PASS",
        scope="Diagnostic computation and source/generation invariants; not full measured qualification",
        evidence_type="measured_recording",
        truth_kind="recorded_proxy",
        counts=dict(counts),
        unique_confirmed_events=list(events.values()),
        invariant_violations=list(violations.values()),
        annotation_confirmation=reviewed,
        contact_matches=matches,
        unmatched_confirmed_table_events=[
            e for e in table_events if (e["generation"], e["id"]) not in matched
        ],
        gaps=gaps,
        unqualified={
            "spin_magnitude_accuracy": "NOT_COVERED: no independent spin truth",
            "physical_false_contact_rate": "INCONCLUSIVE: incomplete position-contact ledger",
            "physical_false_serve_rate": "INCONCLUSIVE: reviewed labels cover only a subset of the take",
            "physical_generation_leakage": "INCONCLUSIVE: racket-to-racket boundaries are unqualified",
            "recovery_command_opportunity_loss": "INCONCLUSIVE: physical eligible-flight denominator is unqualified",
        },
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    annotations = [
        json.loads(line) for line in args.annotations.read_text().splitlines()
    ]
    results = {}
    for profile in (
        "managed",
        "strict",
        "position-only",
        "magnus-off",
        "train-free-flight",
    ):
        for part in (1, 2, 3):
            path = args.root / profile / f"ppq004_part{part}.trace.jsonl"
            ledger = args.root / f"annotations/part{part}/contact_position_ledger.json"
            if not path.exists() or not ledger.exists():
                results[f"{profile}-{part}"] = dict(
                    status="NOT_RUN", reason="Missing trace or position ledger"
                )
                continue
            contacts = [
                dict(
                    source_frame=c["frame"],
                    occurrence_interval_ns=[
                        round((c["frame"] - 4) / 300 * 1e9),
                        round((c["frame"] + 4) / 300 * 1e9),
                    ],
                    occurrence_estimate_ns=round(c["contact_time"] * 1e9),
                    uncertainty_scope="Position-screening bracket ±4 source frames; no independent physical timing claim",
                )
                for c in json.loads(ledger.read_text())["candidates"]
                if not c.get("rejected") and "contact_time" in c
            ]
            labels = [
                a for a in annotations if a["recording_id"] == f"ppq004_part{part}"
            ]
            with path.open() as stream:
                result = diagnose(
                    (json.loads(line) for line in stream), labels, contacts
                )
            result["input_sha256"] = {
                "trace": sha256(path),
                "contact_ledger": sha256(ledger),
                "annotations": sha256(args.annotations),
            }
            results[f"{profile}-{part}"] = result
    result = dict(
        status="FAIL"
        if any(r["status"] == "FAIL" for r in results.values())
        else "INCONCLUSIVE"
        if any(r["status"] != "PASS" for r in results.values())
        else "PASS",
        profiles=results,
    )
    (args.output / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({name: row["status"] for name, row in results.items()}))
    return int(result["status"] == "FAIL")


if __name__ == "__main__":
    raise SystemExit(main())
