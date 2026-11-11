"""Headless reproducible baseline run (no Streamlit).

Usage:
    python scripts/run_baseline.py                      # defaults: 5000 agents, 150 years
    python scripts/run_baseline.py --config data/demo/demo_config.json --out results
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bloodtypelab.config import SimulationConfig  # noqa: E402
from bloodtypelab.engine import simulate  # noqa: E402
from bloodtypelab.exports import export_run  # noqa: E402
from bloodtypelab.validation import validate_run  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", type=Path, help="JSON configuration (as saved by the app)")
    ap.add_argument("--population", type=int)
    ap.add_argument("--years", type=int)
    ap.add_argument("--seed", type=int)
    ap.add_argument("--out", type=Path, default=ROOT / "results")
    args = ap.parse_args()

    cfg = SimulationConfig.from_json(args.config.read_text()) if args.config else SimulationConfig()
    changes = {k: v for k, v in (("initial_population", args.population), ("horizon_steps", args.years), ("seed", args.seed)) if v is not None}
    cfg = replace(cfg, **changes).validate()

    run = simulate(cfg)
    report = validate_run(run)
    folder = export_run(run, args.out)
    s = run.shares()
    print(f"run_id     {run.run_id}")
    print(f"scenario   {run.scenario}   seed {run.seed}   {run.elapsed_seconds:.2f} s")
    print(f"population {int(s.population.iloc[0])} -> {int(s.population.iloc[-1])}")
    for p in ("A", "B", "AB", "O"):
        print(f"  {p:<2} {s[f'share_{p}'].iloc[0] * 100:6.2f} % -> {s[f'share_{p}'].iloc[-1] * 100:6.2f} %")
    print(f"checks     {sum(c.passed for c in report.checks)}/{len(report.checks)} passed")
    print(f"exported   {folder}")
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
