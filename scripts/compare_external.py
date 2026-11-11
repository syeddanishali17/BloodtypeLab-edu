"""Compare complete Java/AnyLogic replicate CSVs with the matching Python configuration."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from bloodtypelab.anylogic_bridge import compare_with_anylogic, python_reference_runs, read_anylogic_output
from bloodtypelab.config import SimulationConfig


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True, help="config.json from the exported bundle")
    parser.add_argument("--results", type=Path, required=True, help="folder containing one CSV per external replicate")
    parser.add_argument("--python-replicates", type=int, default=30)
    parser.add_argument("--report", type=Path, help="optional new report CSV (will not overwrite)")
    args = parser.parse_args()
    files = sorted(args.results.glob("replicate_*.csv"))
    if not files:
        parser.error("No replicate_*.csv files found")
    cfg = SimulationConfig.from_json(args.config.read_text(encoding="utf-8"))
    al = pd.concat([read_anylogic_output(p) for p in files], ignore_index=True)
    report = compare_with_anylogic(al, python_reference_runs(cfg, args.python_replicates))
    print(report.verdict)
    print(report.rows.to_string(index=False))
    for note in report.notes:
        print(note)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open("x", encoding="utf-8", newline="") as out:
            report.rows.to_csv(out, index=False)
    return 0 if report.consistent else 1


if __name__ == "__main__":
    raise SystemExit(main())
