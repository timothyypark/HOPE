"""Independent position-ledger review packets; never read predictor outputs."""

import argparse
import json
from pathlib import Path
import sys
import numpy as np
from ppq004_dataset import sha256, source_ns


def build(source, tools, output):
    output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(tools))
    from refit_ppq_multibounce import position_contacts

    inventory = dict(
        evidence_type="measured_recording",
        truth_kind="recorded_proxy",
        annotation_version="ppq004-independent-v1",
        recordings=[],
        striker_candidates=[],
    )
    episodes = []
    offset = 0
    for part in (1, 2, 3):
        raw = source / f"fit/part{part}/raw_extracted.npz"
        data = dict(np.load(raw, allow_pickle=False))
        (output / f"part{part}").mkdir()
        arcs, contacts, _ = position_contacts(data, part, offset, output)
        offset += len(data["t"]) / 300
        directions = {"positive": 0, "negative": 0, "ambiguous": 0}
        for arc in arcs:
            speed = float((arc["pos"][-1, 0] - arc["pos"][0, 0]) / (arc["t"][-1] - arc["t"][0]))
            direction = "positive" if speed > 0.5 else "negative" if speed < -0.5 else "ambiguous"
            directions[direction] += 1
            frames = np.searchsorted(data["t"], arc["t"])
            episodes.append(
                dict(
                    physical_flight_id=f"part{part}:observed-arc:{arc['id']}",
                    physical_boundary_qualified=False,
                    recording_id=f"ppq004_part{part}",
                    evidence_type="measured_recording",
                    truth_kind="recorded_proxy",
                    parent_sha256=sha256(raw),
                    split="benchmark_holdout" if part == 3 else "development",
                    review_status="INCONCLUSIVE",
                    reviewer="independent_position_screen_v1",
                    annotation_version="ppq004-independent-v1",
                    source_frames=[int(frames[0]), int(frames[-1])],
                    begin_ns=source_ns(arc["t"][0]),
                    end_ns=source_ns(arc["t"][-1]),
                    available_ns=source_ns(arc["t"][-1]),
                    expected_state=None,
                    direction=direction,
                    history_completeness="unknown",
                    reason="Position-qualified arc does not establish preceding physical boundary or serve/rally history",
                    mean_vx_mps=speed,
                    screening=arc["row"],
                )
            )
        for c in contacts:
            vx = float(c["vin_poly"][0])
            x = float(c["contact_xyz"][0])
            if (vx > 0.5 and x < 1.37) or (vx < -0.5 and x > 1.37):
                i = c["frame"]
                begin = max(0, c["pre_start"])
                end = min(len(data["t"]) - 1, c["post_end"])
                inventory["striker_candidates"].append(
                    dict(
                        part=part,
                        source_index=i,
                        original_time_s=float(data["t"][i]),
                        direction="positive" if vx > 0.5 else "negative",
                        parent_sha256=sha256(raw),
                        source_frames=[begin, end],
                        occurrence_interval_ns=[
                            source_ns(data["t"][max(0, i - 4)]),
                            source_ns(data["t"][min(len(data["t"]) - 1, i + 4)]),
                        ],
                        earliest_review_evidence_ns=source_ns(data["t"][end]),
                        contact_position_m=np.asarray(c["contact_xyz"]).tolist(),
                        derivative_window_sensitivity=c.get(
                            "window_sensitivity", c.get("normal_e_window_sensitivity")
                        ),
                        review_status="INCONCLUSIVE",
                        reason="Striker contact candidate; complete serve sequence and boundary require review",
                    )
                )
        inventory["recordings"].append(
            dict(part=part, arcs=len(arcs), contacts=len(contacts), directions=directions)
        )

    def default(value):
        if hasattr(value, "tolist"):
            return value.tolist()
        raise TypeError(type(value).__name__)

    (output / "episodes.jsonl").write_text(
        "".join(json.dumps(e, default=default, allow_nan=False) + "\n" for e in episodes)
    )
    inventory["episodes_sha256"] = sha256(output / "episodes.jsonl")
    (output / "inventory.json").write_text(json.dumps(inventory, indent=2, default=default) + "\n")
    return inventory


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--tools", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(build(a.source, a.tools, a.output), indent=2))


if __name__ == "__main__":
    main()
