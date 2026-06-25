#!/usr/bin/env python3
"""
run_pipeline.py  —  Full F1 prediction pipeline runner.

Stages
------
  0  collect_data.py    Download FastF1 cache + Jolpica CSV  (~30 min first run)
  2  stage2.py          Assemble per-driver-per-race dataset
  3  regressor.py       Train lap-time regressor + Monte Carlo deltas
  4  stage4.py          Train podium classifier + lift metrics

Usage
-----
  python run_pipeline.py                     # full run from scratch
  python run_pipeline.py --skip-download     # skip collect_data (cache already warm)
  python run_pipeline.py --from-stage 3      # resume from regressor
  python run_pipeline.py --year 2023         # pass --year YYYY to collect_data
  python run_pipeline.py --quiet             # suppress per-line stage output
"""

import argparse
import os
import re
import subprocess
import sys
import time


# ── Stage registry ────────────────────────────────────────────────────
# Each stage declares what files it requires (pre-flight check) and
# produces (so the next stage can verify them), plus regex patterns
# that extract summary metrics from its stdout as it runs.
STAGES = [
    {
        "id":      0,
        "name":    "Data Collection",
        "script":  "collect_data.py",
        "desc":    "Download FastF1 cache + Jolpica CSV",
        "requires": [],
        "produces": ["jolpica_raw.csv"],
        "metrics": [
            (r"(\d+/\d+) sessions cached",          "sessions"),
        ],
    },
    {
        "id":      2,
        "name":    "Dataset Assembly",
        "script":  "stage2.py",
        "desc":    "Assemble per-driver-per-race dataset",
        "requires": [],
        "produces": ["stage2_dataset.csv"],
        "metrics": [
            (r"Saved ([\d,]+) rows",                 "rows"),
        ],
    },
    {
        "id":      3,
        "name":    "Lap-Time Regressor",
        "script":  "regressor.py",
        "desc":    "Train lap-time regressor + Monte Carlo deltas",
        "requires": [],
        "produces": ["pace_deltas.csv"],
        "metrics": [
            (r"MAE on \d+ \(held-out\): ([\d.]+) seconds", "MAE"),
            (r"Saved ([\d,]+) driver-race rows",            "delta rows"),
        ],
    },
    {
        "id":      4,
        "name":    "Podium Classifier",
        "script":  "stage4.py",
        "desc":    "Train podium classifier + lift metrics",
        "requires": ["stage2_dataset.csv", "pace_deltas.csv"],
        "produces": [],
        "metrics": [
            (r"Log Loss improvement\s*:\s*([+\-][\d.]+%)", "LogLoss lift"),
            (r"ROC-AUC\s+improvement\s*:\s*([+\-][\d.]+%)", "AUC lift"),
        ],
    },
]

STAGE_IDS = [s["id"] for s in STAGES]


# ── Utilities ─────────────────────────────────────────────────────────
def fmt_time(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s:02d}s"


def stage_header(stage: dict) -> None:
    bar = "─" * 62
    print(f"\n{bar}")
    print(f"  Stage {stage['id']}  ·  {stage['name']}")
    print(f"  {stage['desc']}")
    print(f"{bar}\n", flush=True)


# ── Stage runner ──────────────────────────────────────────────────────
def run_stage(stage: dict, quiet: bool, extra_args: list) -> tuple:
    """
    Run a single pipeline stage as a subprocess.

    Returns (success: bool, elapsed: float, metrics: dict).
    Streams stdout/stderr in real time (unless --quiet).
    Captures key metric lines via the stage's regex patterns.
    On failure, prints the last 10 lines even in --quiet mode.
    """
    # Pre-flight: required upstream files must exist
    missing = [f for f in stage["requires"] if not os.path.exists(f)]
    if missing:
        print(f"  ✗  Pre-flight failed — missing upstream file(s): {', '.join(missing)}")
        print(f"     Re-run from an earlier stage with --from-stage <id>")
        return False, 0.0, {}

    cmd = [sys.executable, stage["script"]] + extra_args
    compiled = [(re.compile(p), lbl) for p, lbl in stage["metrics"]]
    metrics: dict = {}
    tail: list = []

    t0 = time.time()
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    for raw in proc.stdout:
        line = raw.rstrip("\n")
        tail = (tail + [line])[-20:]

        for pattern, label in compiled:
            match = pattern.search(line)
            if match and label not in metrics:
                metrics[label] = match.group(1)

        if not quiet:
            print(f"  {line}", flush=True)

    proc.wait()
    elapsed = time.time() - t0
    success = proc.returncode == 0

    if not success:
        print(f"\n  ✗  Stage {stage['id']} exited with code {proc.returncode}")
        if quiet and tail:
            print("  Last output:")
            for ln in tail[-10:]:
                print(f"    {ln}")

    return success, elapsed, metrics


# ── Summary banner ────────────────────────────────────────────────────
def print_summary(results: list, total: float) -> None:
    """Print the final run-summary table inside a box."""

    # Build display tuples
    rows = []
    for r in results:
        sid    = str(r["stage"]["id"])
        name   = r["stage"]["name"]
        t      = fmt_time(r["elapsed"]) if r["elapsed"] > 0 else "—"
        status = "✓" if r["success"] else "✗  FAILED"
        parts  = [f"{k}: {v}" for k, v in r["metrics"].items()]
        metric = "  ·  ".join(parts) if parts else "—"
        rows.append((f"{sid}  {name}", t, metric, status))

    # Column widths (at least as wide as the column headers)
    cw = [
        max(len("Stage"),      *(len(r[0]) for r in rows)),
        max(len("Time"),       *(len(r[1]) for r in rows)),
        max(len("Key metric"), *(len(r[2]) for r in rows)),
        max(len("Status"),     *(len(r[3]) for r in rows)),
    ]

    def row_str(c0, c1, c2, c3) -> str:
        return (f"  {c0.ljust(cw[0])}"
                f"  {c1.rjust(cw[1])}"
                f"  {c2.ljust(cw[2])}"
                f"  {c3.ljust(cw[3])}"
                f"  ")

    TITLE      = "F1 PIPELINE — RUN SUMMARY"
    total_str  = fmt_time(total)
    ok         = all(r["success"] for r in results)
    verdict    = "✓  ALL STAGES PASSED" if ok else "✗  PIPELINE FAILED"
    footer_str = f"  Total: {total_str}   {verdict}  "
    hdr_str    = row_str("Stage", "Time", "Key metric", "Status")

    width = max(len(hdr_str), len(TITLE) + 4, len(footer_str))

    def line(content: str) -> str:
        return f"║{content.ljust(width)}║"

    E = "═" * width
    D = "─" * width

    print(f"\n╔{E}╗")
    print(line(f"  {TITLE}"))
    print(f"╠{E}╣")
    print(line(hdr_str))
    print(f"╠{D}╣")
    for r_tuple in rows:
        print(line(row_str(*r_tuple)))
    print(f"╠{E}╣")
    print(line(footer_str))
    print(f"╚{E}╝\n")


# ── Argument parsing ──────────────────────────────────────────────────
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run the full F1 prediction pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--from-stage",
        type=int,
        choices=STAGE_IDS,
        default=0,
        metavar=f"{{{','.join(str(i) for i in STAGE_IDS)}}}",
        help="Start from this stage ID (default: 0 — full run).",
    )
    p.add_argument(
        "--skip-download",
        action="store_true",
        help="Alias for --from-stage 2 (FastF1 cache already warm).",
    )
    p.add_argument(
        "--year",
        type=int,
        metavar="YYYY",
        help="Pass --year YYYY to collect_data.py.",
    )
    p.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-line stage output; only show summaries.",
    )
    return p.parse_args()


# ── Main ──────────────────────────────────────────────────────────────
def main() -> None:
    args = parse_args()

    start_id       = 2 if args.skip_download else args.from_stage
    stages_to_run  = [s for s in STAGES if s["id"] >= start_id]
    collect_extras = ["--year", str(args.year)] if args.year else []

    if not stages_to_run:
        sys.exit("No stages to run.")

    ids_str = " → ".join(str(s["id"]) for s in stages_to_run)
    print(f"\n{'═' * 62}")
    print(f"  F1 PREDICTION PIPELINE")
    print(f"  Stages: {ids_str}")
    print(f"{'═' * 62}")

    results       = []
    pipeline_t0   = time.time()
    aborted_early = False

    for stage in stages_to_run:
        stage_header(stage)
        extra   = collect_extras if stage["id"] == 0 else []
        success, elapsed, metrics = run_stage(stage, args.quiet, extra)
        results.append({
            "stage":   stage,
            "success": success,
            "elapsed": elapsed,
            "metrics": metrics,
        })

        if not success:
            # Mark all remaining stages as not-run and stop
            remaining = [s for s in stages_to_run if s["id"] > stage["id"]]
            for s in remaining:
                results.append({"stage": s, "success": False,
                                 "elapsed": 0.0, "metrics": {}})
            aborted_early = True
            break

    total_elapsed = time.time() - pipeline_t0
    print_summary(results, total_elapsed)
    sys.exit(1 if aborted_early else 0)


if __name__ == "__main__":
    main()
