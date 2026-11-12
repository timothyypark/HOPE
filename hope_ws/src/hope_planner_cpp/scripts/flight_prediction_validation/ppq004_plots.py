"""Measured-path/state and proxy error plots bound to one campaign directory."""

import argparse
import csv
import json
from pathlib import Path
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def plots(root):
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
        axes[2].step(t, g, where="post", lw=0.7)
        axes[2].set_ylabel("generation")
        axes[2].set_xlabel("original recording time (s)")
        fig.suptitle(
            f"PPQ004 part {part}: measured path and actual classifier output (not independent labels)"
        )
        fig.tight_layout()
        name = f"part{part}-timeline.png"
        fig.savefig(root / name, dpi=140)
        plt.close(fig)
        figs.append(name)
    path = root / "forecast-managed-benchmark_holdout/errors.csv"
    if path.exists():
        grouped = {}
        with path.open() as f:
            for row in csv.DictReader(f):
                key = int(float(row["lead_ms"]) // 20) * 20
                grouped.setdefault(key, []).append(float(row["position_error_m"]) * 1000)
        if grouped:
            fig, ax = plt.subplots(figsize=(9, 5))
            x = sorted(grouped)
            ax.plot(x, [np.median(grouped[k]) for k in x], label="median")
            ax.plot(x, [np.quantile(grouped[k], 0.95) for k in x], label="95th percentile")
            ax.set(
                xlabel="forecast lead bin (ms)",
                ylabel="position residual (mm)",
                title="Measured holdout proxy residuals; conditional on available forecast",
            )
            ax.legend()
            fig.tight_layout()
            fig.savefig(root / "holdout-error-vs-lead.png", dpi=140)
            plt.close(fig)
            figs.append("holdout-error-vs-lead.png")
    return figs


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("root", type=Path)
    print(json.dumps(plots(p.parse_args().root)))
