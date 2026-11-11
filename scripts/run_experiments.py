"""Headless scenario batch: baseline vs immigration vs disease vs bottleneck (+ optional fitness).

Usage:
    python scripts/run_experiments.py --replicates 20 --population 3000 --years 120 --out results
Writes one folder per run plus experiment_summary.csv (final-year means, bands and paired differences).
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bloodtypelab.config import SimulationConfig  # noqa: E402
from bloodtypelab.experiments import Scenario, default_seeds, endpoint_table, run_scenario_batch  # noqa: E402
from bloodtypelab.exports import export_run  # noqa: E402
from bloodtypelab.selection import preset  # noqa: E402
from bloodtypelab.shocks import bottleneck_shock, disease_shock, immigration_shock  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--replicates", type=int, default=10)
    ap.add_argument("--population", type=int, default=3000)
    ap.add_argument("--years", type=int, default=120)
    ap.add_argument("--seed", type=int, default=20261111)
    ap.add_argument("--shock-year", type=int, default=30)
    ap.add_argument("--fitness", default=None, help="optional selection preset, e.g. o_survival_advantage")
    ap.add_argument("--out", type=Path, default=ROOT / "results")
    args = ap.parse_args()

    base = SimulationConfig(initial_population=args.population, horizon_steps=args.years, seed=args.seed)
    y = args.shock_year
    scenarios = [
        Scenario("baseline", "Baseline"),
        Scenario("immigration", "Immigration", (immigration_shock("high_b_source", start_step=y, count_per_step=args.population // 5),)),
        Scenario("disease", "Disease", (disease_shock(("A",), start_step=y, duration_steps=5, mode="additional_probability",
                                                      additional_probability=0.05),)),
        Scenario("bottleneck", "Bottleneck", (bottleneck_shock(0.5, start_step=y),)),
    ]
    if args.fitness:
        scenarios.append(Scenario("fitness", f"Fitness: {args.fitness}", (), preset(args.fitness)))

    def progress(done: int, total: int, label: str) -> None:
        print(f"\r{done}/{total} runs ({label})        ", end="", flush=True)

    batch = run_scenario_batch(base, scenarios, default_seeds(args.replicates, args.seed), progress=progress)
    print()
    out = args.out / f"experiment_{datetime.now().strftime('%Y%m%dT%H%M%S')}"
    out.mkdir(parents=True)
    for run in batch.all_runs():
        export_run(run, out)
    cols = ["share_A", "share_B", "share_AB", "share_O", "share_a_A", "share_a_B", "share_a_O", "share_rh_neg"]
    summary = endpoint_table(batch, cols)
    summary.to_csv(out / "experiment_summary.csv", index=False)
    print(summary[summary.metric.isin(["share_A", "share_B", "share_O"])].round(2).to_string(index=False))
    print(f"\nInvariants OK in all runs: {batch.invariants_ok}\nWritten to {out}")
    return 0 if batch.invariants_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
