"""Recorded event and wire-lifetime plots; no new truth or qualification verdicts."""

import csv
import json
from pathlib import Path
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def details(root, output=None):
    output = output or root
    figures = []
    for part in (1, 2, 3):
        ledger = root / f"annotations/part{part}/contact_position_ledger.json"
        forecasts = root / f"managed/ppq004_part{part}.forecast.jsonl"
        source = root / f"source/fit/part{part}/raw_extracted.npz"
        if not all(path.exists() for path in (ledger, forecasts, source)):
            continue
        contacts = [
            c
            for c in json.loads(ledger.read_text())["candidates"]
            if not c.get("rejected") and "contact_time" in c
        ]
        if not contacts:
            continue
        # Predeclared display selection: first position-qualified contact in each take.
        event = contacts[0]
        origin = float(event["contact_time"])
        data = dict(np.load(source))
        positions = data["ball_pos"].copy()
        positions[~data["ball_present"]] = np.nan
        window = (data["t"] >= origin - 0.25) & (data["t"] <= origin + 0.25)
        available = []
        with forecasts.open() as stream:
            for line in stream:
                row = json.loads(line)
                delta = row["source_ns"] * 1e-9 - origin
                if (
                    -0.13 <= delta <= 0.08
                    and row["physical_available"]
                    and row["waypoints"]
                    and row["prediction_reference_ns"] == row["source_ns"]
                ):
                    available.append(row)
        fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
        for axis, coordinate, name in ((axes[0], 2, "Z"), (axes[1], 0, "X")):
            axis.plot(
                (data["t"][window] - origin) * 1000,
                positions[window, coordinate],
                color="black",
                label="measured Ball frames",
                lw=1.4,
            )
            axis.axvspan(
                -4 / 300 * 1000,
                4 / 300 * 1000,
                color="grey",
                alpha=0.15,
                label="screening bracket ±4 frames",
            )
            selected = set()
            for target in (-0.1, -0.05, 0.05):
                if not available:
                    continue
                row = min(
                    available,
                    key=lambda r: abs(r["source_ns"] * 1e-9 - origin - target),
                )
                actual = row["source_ns"] * 1e-9 - origin
                if abs(actual - target) > 0.025 or row["source_ns"] in selected:
                    continue
                selected.add(row["source_ns"])
                w = np.asarray(row["waypoints"])
                axis.plot(
                    (row["prediction_reference_ns"] * 1e-9 + w[:, 0] - origin) * 1000,
                    w[:, coordinate + 1],
                    label=f"actual forecast cutoff {actual * 1000:.0f} ms",
                    lw=1,
                )
            if not selected:
                axis.text(
                    0.02,
                    0.95,
                    "No available forecast near requested cutoffs",
                    transform=axis.transAxes,
                    va="top",
                )
            axis.set_ylabel(name + " (m)")
            axis.set_xlim(-250, 250)
            axis.legend(fontsize=8)
        axes[-1].set_xlabel("Time relative to position-qualified contact estimate (ms)")
        fig.suptitle(
            f"Part {part}, source frame {event['frame']}: recorded proxy; no independent event-time claim"
        )
        fig.tight_layout()
        name = f"part{part}-contact-forecasts.png"
        fig.savefig(output / name, dpi=140)
        plt.close(fig)
        figures.append(name)
    raw_path = root / "ros-1-300-fixed/raw.json"
    if raw_path.exists():
        raw = json.loads(raw_path.read_text())
        received = raw["received"]
        epoch = raw["source"].get("epoch_ns", 0)
        candidates = received["candidates"]
        valid = [r for r in candidates if r["supported"]]
        wires = [r for r in received["commands"] if r[1] == 1]
        publication = {}
        with (raw_path.parent / "planner.tsv").open() as stream:
            stream.readline()
            for row in csv.DictReader(stream, delimiter="\t"):
                if row["stage"] == "command_published":
                    publication[int(row["sequence"])] = int(row["wall_ns"])
        fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
        for coordinate, label in ((0, "X"), (1, "Y"), (2, "Z")):
            axes[0].scatter(
                [(r["source_ns"] - epoch) * 1e-9 for r in valid],
                [r["contact"][coordinate] for r in valid],
                s=7,
                label="supported contact " + label,
            )
        if not valid:
            axes[0].text(
                0.02,
                0.9,
                "No supported contact candidates retained",
                transform=axes[0].transAxes,
            )
        axes[0].set_ylabel("Table-frame contact (m)")
        axes[0].legend(fontsize=8)
        axes[1].scatter(
            [(r["source_ns"] - epoch) * 1e-9 for r in valid],
            [(r["contact_ns"] - r["source_ns"]) * 1e-6 for r in valid],
            s=7,
            label="candidate contact lead",
        )
        for wire in wires:
            published = publication.get(int(wire[14]))
            if published is None:
                continue
            axes[1].scatter(
                [(published - epoch) * 1e-9],
                [(wire[10] - published * 1e-9) * 1000],
                marker="x",
                c="red",
            )
        axes[1].axhline(
            80, color="grey", ls="--", label="80 ms software usability reference"
        )
        axes[1].set(
            xlabel="Replay time (s): candidate source time / wire publication time",
            ylabel="Contact lead (ms)",
        )
        axes[1].legend()
        fig.suptitle(
            "Recorded ROS fixed-plane candidates and published commands; eligibility denominator unqualified"
        )
        fig.tight_layout()
        name = "ros-plane-command-timeline.png"
        fig.savefig(output / name, dpi=140)
        plt.close(fig)
        figures.append(name)
        fig, ax = plt.subplots(figsize=(12, 5))
        if not wires:
            ax.text(
                0.5,
                0.5,
                "No valid commands in this trial; consumer lifetime is NOT_COVERED",
                ha="center",
                va="center",
                transform=ax.transAxes,
            )
        for i, wire in enumerate(wires):
            published = publication.get(int(wire[14]))
            if published is None:
                continue
            start = (published - epoch) * 1e-9
            end = wire[10] - epoch * 1e-9
            ax.plot([start, end], [i, i], marker="|", color="steelblue")
            for decoded in received["decoded"]:
                if (
                    decoded[0] == wire[14]
                    and decoded[1] == wire[15]
                    and decoded[10] == 0
                ):
                    ax.scatter(
                        [decoded[13] + decoded[14] * 1e-9 - epoch * 1e-9],
                        [i],
                        c="green",
                        marker="o",
                    )
            for revoke in received["revocations"]:
                if (
                    revoke["command_sequence"] == wire[14]
                    and revoke["command_flight"] == wire[15]
                    and revoke["home"] == wire[19]
                ):
                    ax.scatter(
                        [(revoke["published_ns"] - epoch) * 1e-9],
                        [i],
                        c="red",
                        marker="x",
                    )
        ax.set(
            xlabel="Replay-relative wall clock (s)",
            ylabel="Published command ordinal",
            title="Wire publication→deadline; green: decode, red: matching revocation (no policy-engagement inference)",
        )
        fig.tight_layout()
        name = "ros-wire-lifetimes.png"
        fig.savefig(output / name, dpi=140)
        plt.close(fig)
        figures.append(name)
    return figures


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    print(json.dumps(details(parser.parse_args().root)))
