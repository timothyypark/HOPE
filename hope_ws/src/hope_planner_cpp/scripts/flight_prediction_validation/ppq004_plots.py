"""Measured-path/state and proxy error plots bound to one campaign directory."""

import argparse
import csv
import json
from pathlib import Path
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def plots(root, output=None):
    output = output or root
    states = ["INVALID", "OPPONENT_RALLY", "RALLY", "OPPONENT_SERVE", "SERVE"]
    figs = []
    for part in (1, 2, 3):
        raw = root / f"source/fit/part{part}/raw_extracted.npz"
        trace = root / f"managed/ppq004_part{part}.trace.jsonl"
        if not raw.exists() or not trace.exists():
            continue
        data = dict(np.load(raw))
        p = data["ball_pos"].copy()
        p[~data["ball_present"]] = np.nan
        fig, axes = plt.subplots(3, 1, figsize=(14, 8), sharex=True)
        axes[0].plot(data["t"], p[:, 0], lw=0.5, label="measured X")
        axes[0].plot(data["t"], p[:, 2], lw=0.5, label="measured Z")
        ledger = root / f"annotations/part{part}/contact_position_ledger.json"
        if ledger.exists():
            contacts = [
                c
                for c in json.loads(ledger.read_text())["candidates"]
                if not c.get("rejected") and "contact_time" in c
            ]
            for i, contact in enumerate(contacts):
                axes[0].axvline(
                    contact["contact_time"],
                    color="orange",
                    lw=0.4,
                    alpha=0.6,
                    label="position-screened contact" if i == 0 else None,
                )
        axes[0].legend()
        axes[0].set_ylabel("metres")
        t = []
        s = []
        g = []
        for line in trace.open():
            row = json.loads(line)
            if row["phase"] == "after":
                t.append(row["source_ns"] * 1e-9)
                s.append(states.index(row["play_state"]))
                g.append(row["generation"])
        axes[1].step(t, s, where="post", lw=0.7)
        axes[1].set_yticks(range(5), states)
        axes[1].set_ylabel("actual public state")
        annotation_path = (
            Path(__file__).resolve().parents[2]
            / "test/fixtures/ppq004/reviewed_intervals.jsonl"
        )
        if annotation_path.exists():
            for line in annotation_path.read_text().splitlines():
                annotation = json.loads(line)
                if annotation["recording_id"] != f"ppq004_part{part}":
                    continue
                if (
                    annotation["review_status"] == "REVIEWED"
                    and annotation["expected_state"]
                ):
                    axes[1].plot(
                        [
                            annotation["available_ns"] * 1e-9,
                            annotation["end_ns"] * 1e-9,
                        ],
                        [states.index(annotation["expected_state"])] * 2,
                        color="red",
                        lw=3,
                    )
                else:
                    axes[1].axvspan(
                        annotation["begin_ns"] * 1e-9,
                        annotation["end_ns"] * 1e-9,
                        color="grey",
                        alpha=0.3,
                    )
            axes[1].set_title(
                "Red: reviewed proxy state after availability; grey: ambiguous interval",
                fontsize=9,
            )
        axes[2].step(t, g, where="post", lw=0.7)
        axes[2].set_ylabel("generation")
        axes[2].set_xlabel("original recording time (s)")
        fig.suptitle(
            f"PPQ004 part {part}: measured path and actual classifier output (not independent labels)"
        )
        fig.tight_layout()
        name = f"part{part}-timeline.png"
        fig.savefig(output / name, dpi=140)
        plt.close(fig)
        figs.append(name)
    path = root / "forecast-managed-benchmark_holdout/errors.csv"
    if path.exists():
        grouped = {}
        with path.open() as f:
            for row in csv.DictReader(f):
                key = int(float(row["lead_ms"]) // 20) * 20
                grouped.setdefault(key, []).append(
                    float(row["position_error_m"]) * 1000
                )
        if grouped:
            fig, ax = plt.subplots(figsize=(9, 5))
            x = sorted(grouped)
            ax.plot(x, [np.median(grouped[k]) for k in x], label="median")
            ax.plot(
                x, [np.quantile(grouped[k], 0.95) for k in x], label="95th percentile"
            )
            ax.set(
                xlabel="forecast lead bin (ms)",
                ylabel="position residual (mm)",
                title="Measured holdout proxy residuals; conditional on available forecast",
            )
            ax.legend()
            fig.tight_layout()
            fig.savefig(output / "holdout-error-vs-lead.png", dpi=140)
            plt.close(fig)
            figs.append("holdout-error-vs-lead.png")
    receipts = [
        (p.parent.name, json.loads(p.read_text()))
        for p in sorted(root.glob("ros-*/result.json"))
    ]
    if receipts:
        labels = [name for name, _ in receipts]
        stages = [
            "relay_receipt",
            "typed_published",
            "planner_received",
            "tracker_accepted",
        ]
        fig, axes = plt.subplots(2, 1, figsize=(15, 10), sharex=True)
        for stage in stages:
            axes[0].plot(
                range(len(labels)),
                [r.get("loss_by_boundary", {}).get(stage, np.nan) for _, r in receipts],
                marker=".",
                label=stage,
            )
        axes[0].set_ylabel("Offered Ball frames absent at boundary")
        ledger = root / f"annotations/part{part}/contact_position_ledger.json"
        if ledger.exists():
            contacts = [
                c
                for c in json.loads(ledger.read_text())["candidates"]
                if not c.get("rejected") and "contact_time" in c
            ]
            for i, contact in enumerate(contacts):
                axes[0].axvline(
                    contact["contact_time"],
                    color="orange",
                    lw=0.4,
                    alpha=0.6,
                    label="position-screened contact" if i == 0 else None,
                )
        axes[0].legend()
        axes[1].plot(
            range(len(labels)),
            [r.get("valid_commands", 0) for _, r in receipts],
            marker="o",
            label="valid commands",
        )
        axes[1].plot(
            range(len(labels)),
            [r.get("decoded", 0) for _, r in receipts],
            marker=".",
            label="decoder status messages (including revocation updates)",
        )
        axes[1].set_ylabel("Count; physical-flight denominator unqualified")
        axes[1].set_xticks(range(len(labels)), labels, rotation=90, fontsize=7)
        axes[1].legend()
        fig.suptitle(
            "Recorded pipeline losses and outputs; tracker rejection is not necessarily transport loss"
        )
        fig.tight_layout()
        fig.savefig(output / "ros-boundaries.png", dpi=140)
        plt.close(fig)
        figs.append("ros-boundaries.png")
    from ppq004_detail_plots import details

    return figs + details(root, output)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("root", type=Path)
    print(json.dumps(plots(p.parse_args().root)))
