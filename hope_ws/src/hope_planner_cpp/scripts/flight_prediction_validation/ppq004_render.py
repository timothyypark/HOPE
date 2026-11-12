"""Render additional plots into a new directory without changing frozen receipts."""

import argparse
import html
import json
import os
from pathlib import Path
import subprocess
from ppq004_dataset import sha256
from ppq004_plots import plots
from ppq004_report import report


def render(root, output, supplementary=()):
    source = Path(__file__).resolve().parents[5]
    results = json.loads((root / "results.json").read_text())
    if not results.get("completed_ns"):
        raise ValueError("The campaign must finish before the review is rendered")
    annotation = (
        source
        / "hope_ws/src/hope_planner_cpp/test/fixtures/ppq004/reviewed_intervals.jsonl"
    )
    if sha256(annotation) != results["campaign"]["annotation_sha256"]:
        raise ValueError("Current annotation differs from the frozen campaign")
    output.mkdir(parents=True, exist_ok=False)
    receipt = dict(
        campaign_source_sha=results["campaign"]["source_sha"],
        renderer_source_sha=subprocess.check_output(
            ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
        ).strip(),
        renderer_dirty=bool(
            subprocess.check_output(
                ["git", "-C", str(source), "status", "--porcelain"], text=True
            ).strip()
        ),
        original_results_sha256=sha256(root / "results.json"),
        scope="Additional visualization only; no changed raw gate verdicts",
    )
    receipt["figures"] = plots(root, output)
    report(root, output)
    receipt["supplementary_sha256"] = {}
    links = []
    for path in supplementary:
        receipt["supplementary_sha256"][str(path)] = sha256(path)
        links.append(
            '<li><a href="'
            + html.escape(os.path.relpath(path, output), quote=True)
            + '">'
            + html.escape(path.parent.name + "/" + path.name)
            + "</a></li>"
        )
    if links:
        page = output / "index.html"
        page.write_text(
            page.read_text()
            + "<h2>Follow-up evidence</h2><p>Separate invocations; the frozen campaign above retains its original source and verdicts.</p><ul>"
            + "".join(links)
            + "</ul>"
        )
    receipt["output_sha256"] = {
        p.name: sha256(p) for p in output.iterdir() if p.is_file()
    }
    (output / "render-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--supplementary", action="append", type=Path, default=[])
    args = parser.parse_args()
    print(
        json.dumps(
            render(
                args.root.resolve(),
                args.output.resolve(),
                [p.resolve() for p in args.supplementary],
            ),
            indent=2,
        )
    )
