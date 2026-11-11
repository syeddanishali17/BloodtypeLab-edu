"""Replicated, paired scenario experiments.

Design: every scenario is run with the same list of seeds. Because the initial population
uses its own random stream, seed s produces an identical starting population in every
scenario; differences to the baseline are computed per seed (paired) and then summarised.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Callable

import numpy as np
import pandas as pd

from .config import MAX_AGENT_YEARS_BATCH, ConfigError, SelectionConfig, ShockConfig, SimulationConfig
from .engine import RunResult, simulate
from .metrics import add_shares
from .reference import ReferenceData


@dataclass(frozen=True)
class Scenario:
    name: str
    label: str
    shocks: tuple[ShockConfig, ...] = ()
    selection: SelectionConfig | None = None  # None -> keep base config selection
    description: str = ""

    def apply(self, base: SimulationConfig, seed: int) -> SimulationConfig:
        cfg = replace(base, seed=int(seed), scenario=self.name, shocks=tuple(self.shocks))
        if self.selection is not None:
            cfg = replace(cfg, selection=self.selection)
        return cfg


@dataclass
class BatchResult:
    base_config: SimulationConfig
    scenarios: list[Scenario]
    seeds: list[int]
    runs: dict[str, list[RunResult]] = field(default_factory=dict)
    baseline: str = "baseline"

    def shares(self, scenario: str) -> list[pd.DataFrame]:
        return [r.shares() for r in self.runs[scenario]]

    def all_runs(self) -> list[RunResult]:
        return [r for rs in self.runs.values() for r in rs]

    @property
    def invariants_ok(self) -> bool:
        return all(r.invariants_ok for r in self.all_runs())


def run_replicates(config: SimulationConfig, seeds: list[int], reference: ReferenceData | None = None) -> list[RunResult]:
    return [simulate(replace(config, seed=int(s)), reference) for s in seeds]


def check_batch_size(base: SimulationConfig, scenarios: list[Scenario], seeds: list[int]) -> float:
    load = sum(sc.apply(base, 0).estimated_agent_years() for sc in scenarios) * len(seeds)
    if load > MAX_AGENT_YEARS_BATCH:
        raise ConfigError(
            f"Batch too large (~{load:.2g} agent-years > {MAX_AGENT_YEARS_BATCH:.0g}). "
            "Reduce replicates, population or horizon."
        )
    return load


def run_scenario_batch(
    base_config: SimulationConfig,
    scenarios: list[Scenario],
    seeds: list[int],
    reference: ReferenceData | None = None,
    progress: Callable[[int, int, str], None] | None = None,
) -> BatchResult:
    if not scenarios:
        raise ConfigError("Select at least one scenario.")
    if len(set(seeds)) != len(seeds) or not seeds:
        raise ConfigError("Seeds must be a non-empty list of distinct integers.")
    check_batch_size(base_config, scenarios, seeds)
    for sc in scenarios:  # validate everything before running anything
        sc.apply(base_config, seeds[0]).validate()
    batch = BatchResult(base_config, list(scenarios), list(seeds))
    total = len(scenarios) * len(seeds)
    done = 0
    for sc in scenarios:
        batch.runs[sc.name] = []
        for s in seeds:
            batch.runs[sc.name].append(simulate(sc.apply(base_config, s), reference))
            done += 1
            if progress:
                progress(done, total, sc.label)
    batch.baseline = scenarios[0].name if "baseline" not in batch.runs else "baseline"
    return batch


def stack_metric(runs: list[RunResult], column: str) -> pd.DataFrame:
    """Steps x seeds matrix of a share or count column."""
    data = {}
    for i, r in enumerate(runs):  # columns keyed by position (seed alone is not unique when dynamics_seed varies)
        data[i] = r.shares().set_index("step")[column]
    return pd.DataFrame(data)


def summarize_replicates(runs: list[RunResult], column: str) -> pd.DataFrame:
    """Mean, median and empirical 2.5 / 97.5 percentiles across replicates per step."""
    m = stack_metric(runs, column)
    arr = m.to_numpy(dtype=float)
    with np.errstate(all="ignore"):
        out = pd.DataFrame(
            {
                "step": m.index.values,
                "mean": np.nanmean(arr, axis=1),
                "median": np.nanmedian(arr, axis=1),
                "p025": np.nanpercentile(arr, 2.5, axis=1),
                "p975": np.nanpercentile(arr, 97.5, axis=1),
                "sd": np.nanstd(arr, axis=1, ddof=1) if arr.shape[1] > 1 else np.zeros(arr.shape[0]),
                "n": np.sum(~np.isnan(arr), axis=1),
            }
        )
    return out


def paired_differences(batch: BatchResult, scenario: str, column: str, scale: float = 1.0) -> pd.DataFrame:
    """Per-seed scenario minus baseline, summarised (multiply by 100 for percentage points)."""
    base = stack_metric(batch.runs[batch.baseline], column)
    other = stack_metric(batch.runs[scenario], column)
    diff = (other - base) * scale  # paired by position: both scenarios use the same seed list
    arr = diff.to_numpy(dtype=float)
    with np.errstate(all="ignore"):
        return pd.DataFrame(
            {
                "step": diff.index.values,
                "mean": np.nanmean(arr, axis=1),
                "p025": np.nanpercentile(arr, 2.5, axis=1),
                "p975": np.nanpercentile(arr, 97.5, axis=1),
                "sd": np.nanstd(arr, axis=1, ddof=1) if arr.shape[1] > 1 else np.zeros(arr.shape[0]),
            }
        )


def endpoint_table(batch: BatchResult, columns: list[str], step: int | None = None, scale: float = 100.0) -> pd.DataFrame:
    """Summary at one step: mean and band per scenario plus paired difference vs baseline."""
    rows = []
    for sc in batch.scenarios:
        runs = batch.runs[sc.name]
        for col in columns:
            m = stack_metric(runs, col)
            st = m.index.max() if step is None else step
            vals = m.loc[st].to_numpy(dtype=float) * scale
            row = {
                "scenario": sc.label,
                "metric": col,
                "step": int(st),
                "mean": float(np.nanmean(vals)),
                "p025": float(np.nanpercentile(vals, 2.5)),
                "p975": float(np.nanpercentile(vals, 97.5)),
            }
            if sc.name != batch.baseline:
                d = paired_differences(batch, sc.name, col, scale)
                drow = d[d.step == st].iloc[0]
                row.update({"diff_mean": float(drow["mean"]), "diff_p025": float(drow["p025"]), "diff_p975": float(drow["p975"])})
            else:
                row.update({"diff_mean": 0.0, "diff_p025": 0.0, "diff_p975": 0.0})
            rows.append(row)
    return pd.DataFrame(rows)


def batch_long_table(batch: BatchResult) -> pd.DataFrame:
    """All runs, all steps, wide counts + shares, with scenario/seed columns."""
    frames = []
    for name, runs in batch.runs.items():
        for r in runs:
            s = r.shares().copy()
            s.insert(0, "seed", r.seed)
            s.insert(0, "scenario", name)
            s.insert(0, "run_id", r.run_id)
            frames.append(s)
    return pd.concat(frames, ignore_index=True)


def default_seeds(n: int, base_seed: int = 20261111) -> list[int]:
    return [int(base_seed + i) for i in range(n)]
