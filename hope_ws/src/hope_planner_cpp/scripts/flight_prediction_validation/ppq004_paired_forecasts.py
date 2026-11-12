"""Pair ablations at identical measured cutoffs and future frames, grouped by arc."""

import argparse
import csv
import json
from pathlib import Path
import numpy as np
from ppq004_dataset import sha256


def load_rows(path):
    rows = {}
    with path.open() as stream:
        for row in csv.DictReader(stream):
            key = tuple(
                row[k] for k in ("recording_id", "arc_id", "source_ns", "truth_ns")
            )
            if key in rows:
                raise ValueError("Duplicate forecast/truth identity")
            rows[key] = float(row["position_error_m"])
    return rows


def compare(reference, candidate):
    shared = reference.keys() & candidate.keys()
    groups = {}
    for key in sorted(shared):
        groups.setdefault(key[:2], []).append((reference[key], candidate[key]))
    arcs = []
    for (recording, arc), values in groups.items():
        rms = np.sqrt(np.mean(np.square(values), axis=0))
        arcs.append(
            dict(
                recording_id=recording,
                arc_id=arc,
                paired_samples=len(values),
                reference_rms_m=float(rms[0]),
                candidate_rms_m=float(rms[1]),
                difference_m=float(rms[1] - rms[0]),
            )
        )
    deltas = [row["difference_m"] for row in arcs]
    rng = np.random.default_rng(1226)
    boot = (
        [
            float(np.median(rng.choice(deltas, len(deltas), replace=True)))
            for _ in range(1000)
        ]
        if deltas
        else []
    )
    return dict(
        status="PASS" if arcs else "NOT_COVERED",
        paired_arcs=arcs,
        reference_samples=len(reference),
        candidate_samples=len(candidate),
        paired_samples=len(shared),
        reference_only=len(reference.keys() - candidate.keys()),
        candidate_only=len(candidate.keys() - reference.keys()),
        median_paired_arc_difference_m=float(np.median(deltas)) if deltas else None,
        bootstrap_95_m=np.quantile(boot, [0.025, 0.975]).tolist() if boot else None,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    comparisons = {}
    hashes = {}
    for split in ("development", "benchmark_holdout"):
        baseline = args.root / f"forecast-managed-{split}/errors.csv"
        for profile in ("position-only", "magnus-off", "train-free-flight"):
            candidate = args.root / f"forecast-{profile}-{split}/errors.csv"
            key = f"{profile}-{split}"
            if not baseline.exists() or not candidate.exists():
                comparisons[key] = dict(status="NOT_RUN", reason="Missing input scores")
                continue
            hashes[str(baseline.relative_to(args.root))] = sha256(baseline)
            hashes[str(candidate.relative_to(args.root))] = sha256(candidate)
            comparisons[key] = compare(load_rows(baseline), load_rows(candidate))
    result = dict(
        status="PASS"
        if all(c["status"] == "PASS" for c in comparisons.values())
        else "INCONCLUSIVE",
        evidence_type="measured_recording",
        truth_kind="recorded_proxy",
        scope="Paired diagnostic computation; no physics adoption decision",
        uncertainty_unit="screened arc, not independent session or qualified physical flight",
        comparisons=comparisons,
        input_sha256=hashes,
    )
    (args.output / "results.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
