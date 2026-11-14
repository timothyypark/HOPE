"""Standalone evidence index: every gate links to retained receipts and failures."""

import argparse
import html
from fnmatch import fnmatch
import json
import os
from pathlib import Path


REQUIREMENT_GATES = {
    "DATA": ["data-integrity", "prepare", "scorer-controls"],
    "CLOCK": [
        "scorer-controls",
        "ros-fault-clock_backstep/fault-response",
        "ros-fault-duplicate/fault-response",
    ],
    "ANNOTATION": ["annotations", "state-managed-*", "state-strict-*"],
    "STATE": ["controlled-states", "integrated/native-test"],
    "REPLAY": ["managed", "strict"],
    "TRACE": ["scorer-controls", "ros-full-take-*"],
    "EVENT": ["integrated/native-test", "event-spin-diagnostics"],
    "SPIN": [
        "event-spin-diagnostics",
        "integrated/native-test",
        "position-only",
        "managed",
        "ros-fault-missing_orientation/fault-response",
        "ros-fault-quaternion_sign/fault-response",
    ],
    "FORECAST": ["forecast-*", "paired-forecasts", "public-plane-comparison"],
    "PLANE": [
        "integrated/native-test",
        "ros-*-per_ball",
        "ros-*-stable_per_ball",
        "ros-fault-home_change/fault-response",
    ],
    "COMMAND": ["conversion", "complete-command-opportunities"],
    "PREFIX": [
        "integrated/native-test",
        "ros-fault-typed_loss/fault-response",
        "ros-fault-typed_delay/fault-response",
    ],
    "RUNNER": ["runner-lifecycle"],
    "ROS": ["ros-*-150-*", "ros-*-300-*", "ros-fault-*", "ros-full-take-*"],
    "LOSS": ["historical-loss-closure"],
    "OUTGOING": ["outgoing-mujoco"],
    "COUPLED": ["coupled-scenario-*"],
    "PHYSICAL": ["physical-qualification"],
}


def requirement_results(gates, requirements):
    """Conservative accounting: a missing planned gate cannot become a pass."""
    rows = []
    for requirement in requirements:
        patterns = REQUIREMENT_GATES.get(requirement["id"], [])
        selected = {
            name: gate["status"]
            for name, gate in gates.items()
            if any(fnmatch(name, pattern) for pattern in patterns)
        }
        missing = [
            pattern
            for pattern in patterns
            if not any(fnmatch(name, pattern) for name in gates)
        ]
        states = list(selected.values()) + (
            ["NOT_RUN"] if missing or not patterns else []
        )
        status = next(
            (
                state
                for state in ("FAIL", "NOT_RUN", "INCONCLUSIVE", "NOT_COVERED")
                if state in states
            ),
            "PASS",
        )
        rows.append(
            dict(
                requirement,
                status=status,
                gates=selected,
                missing_gate_patterns=missing,
            )
        )
    return rows


def receipt_link(root, name, gate):
    candidates = [
        root / name / "result.json",
        root / name / "results.json",
        root / name / "receipt.json",
    ]
    if gate["status"] == "FAIL":
        candidates = [
            path
            for path in sorted((root / name).glob("*.stderr"))
            if path.stat().st_size
        ] + candidates
    if name.startswith("state-"):
        candidates.append(root / ("state-score-" + name[len("state-") :] + ".json"))
    if gate.get("log"):
        candidates.extend(
            [root / gate["log"], (root / gate["log"]).with_suffix(".exit")]
        )
    candidates.append(root / "results.json")
    return next(path for path in candidates if path.is_file())


def report(root, output=None):
    output = output or root

    def href(path):
        return html.escape(os.path.relpath(path, output), quote=True)

    results = json.loads((root / "results.json").read_text())
    rows = []
    for name, gate in results["gates"].items():
        link = href(receipt_link(root, name, gate))
        rows.append(
            "<tr><td>"
            + html.escape(name)
            + "</td><td>"
            + html.escape(gate["status"])
            + "</td><td>"
            + html.escape(gate.get("evidence_type", "software_fixture"))
            + '</td><td><a href="'
            + link
            + '">raw receipt</a></td><td>'
            + html.escape(gate.get("reason", ""))
            + "</td></tr>"
        )
    requirement_table = "".join(
        "<tr><td>"
        + html.escape(row["id"])
        + "</td><td>"
        + html.escape(row["status"])
        + "</td><td>"
        + html.escape(row["completion_condition"])
        + "</td><td>"
        + html.escape(", ".join(row["gates"]))
        + "</td></tr>"
        for row in results.get("requirements", [])
    )
    state_sections = []
    for path in sorted(root.glob("state-score-*.json")):
        s = json.loads(path.read_text())
        matrix = s.get("confusion_matrix", {})
        state_sections.append(
            "<details><summary>"
            + html.escape(path.name)
            + "</summary><pre>"
            + html.escape(json.dumps(matrix, indent=2))
            + "</pre></details>"
        )
    # Compact actual trace timelines retain source frame indices for review.
    timeline = []
    for path in sorted((root / "managed").glob("*.trace.jsonl")):
        previous = None
        with path.open() as f:
            for line in f:
                r = json.loads(line)
                if r["phase"] != "after":
                    continue
                if r["play_state"] != previous:
                    timeline.append(
                        dict(
                            recording=path.stem,
                            source_index=r["source_index"],
                            source_ns=r["source_ns"],
                            state=r["play_state"],
                            generation=r["generation"],
                            reason=r["reason"],
                        )
                    )
                    previous = r["play_state"]
    payload = json.dumps(timeline).replace("<", "\\u003c")
    figures = "".join(
        '<figure><img style="max-width:100%" src="'
        + href(p)
        + '"><figcaption>'
        + html.escape(p.name)
        + "</figcaption></figure>"
        for p in sorted(
            {p.name: p for p in [*root.glob("*.png"), *output.glob("*.png")]}.values()
        )
    )
    text = (
        """<!doctype html><meta charset="utf-8"><title>PPQ004 validation evidence</title>
<style>body{font:16px system-ui;max-width:1200px;margin:32px auto;padding:0 20px}table{border-collapse:collapse;width:100%}td,th{padding:8px;border-bottom:1px solid #ddd;text-align:left}pre{white-space:pre-wrap}a{color:#1254a1}select{padding:8px}</style>
<h1>PPQ004 validation evidence</h1><p>Recorded proxy, controlled fixtures, simulation and physical evidence are separate. Missing evidence never counts as a pass.</p>
<p><a href="RESULTS_LINK">Machine-readable results and source binding</a> · <a href="CAMPAIGN_LINK">Frozen campaign</a></p>
<table><thead><tr><th>Gate</th><th>Status</th><th>Evidence</th><th>Receipt</th><th>Limits</th></tr></thead><tbody>"""
        + "".join(rows)
        + "</tbody></table><h2>Requirement coverage</h2><table><tr><th>Requirement</th><th>Status</th><th>Completion condition</th><th>Evidence gates</th></tr>"
        + requirement_table
        + """</table>
<h2>Measured paths and forecasts</h2>"""
        + figures
        + """<h2>Measured classification</h2>"""
        + "".join(state_sections)
        + """
<h2>Actual state transitions</h2><p>Observed classifier transitions are not independent truth labels. Select a state to locate its recording and original source frame.</p><select id="filter"><option>All</option><option>INVALID</option><option>RALLY</option><option>OPPONENT_RALLY</option><option>SERVE</option><option>OPPONENT_SERVE</option></select><pre id="timeline"></pre>
<script>const data="""
        + payload
        + """;const filter=document.getElementById('filter');function draw(){document.getElementById('timeline').textContent=data.filter(r=>filter.value==='All'||r.state===filter.value).map(r=>JSON.stringify(r)).join('\\n')}filter.onchange=draw;draw();</script>"""
    )
    text = text.replace("RESULTS_LINK", href(root / "results.json")).replace(
        "CAMPAIGN_LINK", href(root / "campaign.json")
    )
    (output / "index.html").write_text(text)
    return output / "index.html"


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("root", type=Path)
    report(p.parse_args().root)
