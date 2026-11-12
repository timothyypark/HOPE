"""Causal recorded-proxy state scorer; annotations never enter the predictor."""

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

STATES = ("INVALID", "OPPONENT_RALLY", "RALLY", "OPPONENT_SERVE", "SERVE")


def validate_annotation(row):
    required = (
        "physical_flight_id",
        "recording_id",
        "evidence_type",
        "parent_sha256",
        "review_status",
        "reviewer",
        "annotation_version",
        "source_frames",
        "begin_ns",
        "end_ns",
        "available_ns",
        "expected_state",
        "history_completeness",
    )
    for key in required:
        if key not in row:
            raise ValueError("annotation missing " + key)
    if row["expected_state"] not in (*STATES, None):
        raise ValueError("unknown expected state")
    if row["end_ns"] < row["begin_ns"] or not row["source_frames"]:
        raise ValueError("invalid annotation interval/provenance")
    if row["available_ns"] < row["begin_ns"]:
        raise ValueError("annotation availability precedes its evidence interval")
    if row["review_status"] == "REVIEWED" and not row["reviewer"]:
        raise ValueError("reviewed label requires reviewer")


def score(trace, annotations, expected_frames):
    for row in annotations:
        validate_annotation(row)
    matrix = {s: {t: 0 for t in STATES} for s in STATES}
    classification = Counter()
    reasons = Counter()
    observed = Counter()
    transitions = Counter()
    phase_counts = defaultdict(list)
    previous = None
    seq = 0
    footer = False
    scored = 0
    unscored = 0
    for row in trace:
        if footer:
            raise ValueError("data after trace footer")
        seq += 1
        if row.get("trace_sequence") != seq:
            raise ValueError("missing/reordered trace sequence")
        if row["phase"] == "footer":
            if row.get("frames") != expected_frames or row.get("complete") is not True:
                raise ValueError("incomplete trace footer")
            footer = True
            continue
        index = row["source_index"]
        if row["phase"] in ("before", "after_expire", "after"):
            phase_counts[index].append(row["phase"])
        if row["phase"] != "after":
            continue
        state = row["play_state"]
        if state not in STATES:
            raise ValueError("unknown public state")
        observed[state] += 1
        classification[row["classification_status"]] += 1
        reasons[row["reason"]] += 1
        if previous is not None and previous != state:
            transitions[previous + "->" + state] += 1
        previous = state
        labels = [
            a
            for a in annotations
            if a["review_status"] == "REVIEWED"
            and a["expected_state"] is not None
            and a["begin_ns"] <= row["source_ns"] <= a["end_ns"]
            and a["available_ns"] <= row["source_ns"]
        ]
        if len({a["expected_state"] for a in labels}) > 1:
            raise ValueError("conflicting annotations")
        if not labels:
            unscored += 1
            continue
        matrix[labels[0]["expected_state"]][state] += 1
        scored += 1
    if not footer:
        raise ValueError("missing trace completion footer")
    if set(phase_counts) != set(range(expected_frames)) or any(
        phases != ["before", "after_expire", "after"] for phases in phase_counts.values()
    ):
        raise ValueError("incomplete/duplicate frame phases")
    per_state = {}
    for state in STATES:
        support = sum(matrix[state].values())
        predicted = sum(matrix[s][state] for s in STATES)
        per_state[state] = dict(
            status="NOT_COVERED"
            if not support
            else "PASS"
            if matrix[state][state] == support and predicted == support
            else "FAIL",
            support=support,
            precision=matrix[state][state] / predicted if predicted else None,
            recall=matrix[state][state] / support if support else None,
        )
    return dict(
        evidence_type="measured_recording",
        truth_kind="recorded_proxy",
        trace_complete=True,
        frames=expected_frames,
        scored_frames=scored,
        unscored_frames=unscored,
        verdict="NOT_COVERED"
        if not scored
        else "FAIL"
        if any(s["status"] == "FAIL" for s in per_state.values())
        else "PASS",
        confusion_matrix=matrix,
        states=per_state,
        observed_states=dict(observed),
        observed_transitions=dict(transitions),
        classification_counts=dict(classification),
        reasons=dict(reasons),
        transition_qualification="INCONCLUSIVE: observed transitions are not independently labeled transitions",
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--trace", type=Path, required=True)
    p.add_argument("--annotations", type=Path, required=True)
    p.add_argument("--frames", type=int, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--recording-id", required=True)
    a = p.parse_args()
    with a.trace.open() as f:
        labels = [json.loads(line) for line in a.annotations.read_text().splitlines()]
        labels = [row for row in labels if row["recording_id"] == a.recording_id]
        result = score((json.loads(line) for line in f), labels, a.frames)
        result["recording_id"] = a.recording_id
    a.output.write_text(json.dumps(result, indent=2) + "\n")
    return int(result["verdict"] == "FAIL")


if __name__ == "__main__":
    raise SystemExit(main())
