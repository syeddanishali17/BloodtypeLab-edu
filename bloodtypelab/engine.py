"""The single authoritative time-stepped agent-based engine.

Chronology of one year (step t = 1..H)
--------------------------------------
1. Immigration     scheduled immigrants join with their sampled ages.
2. Mortality       one Bernoulli draw per agent with the combined probability
                   q = 1 - (1 - q_base*)(1 - q_disease)(1 - q_bottleneck), where q_base* already
                   includes the fitness hazard multiplier. Deaths are attributed to causes by
                   partitioning the same uniform draw (natural -> disease -> bottleneck).
3. Ageing          survivors age by one year.
4. Reproduction    each eligible woman gives birth with probability f(age) x fecundity x regulation
                   (max one child per year); the father is a random eligible man (weighted by
                   fecundity). Child: paternal allele from father, maternal allele from mother,
                   optional mutation. Optional Rh-HDN pregnancy loss.
5. Newborns        added at age 0; cannot reproduce in their birth year.
6. Metrics         counts recorded; accounting invariants checked.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

import numpy as np
import pandas as pd

from . import __version__
from .agents import FEMALE, MALE, Population
from .config import SimulationConfig
from .demography import fertility_schedule, mortality_schedule, regulation_factor
from .genetics import mutate_alleles, transmit_alleles
from .initialization import InitializationResult, initialize_population
from .metrics import ALL_COLUMNS, add_shares, count_row
from .reference import ReferenceData, load_reference
from .selection import FitnessArrays, apply_relative_risk
from .shocks import apply_disease, make_immigrants

ProgressFn = Callable[[int, int], None]


class InvariantError(RuntimeError):
    pass


@dataclass
class RunResult:
    run_id: str
    config: SimulationConfig
    config_hash: str
    reference: dict
    inference: dict
    initial_comparison: list[dict]
    timeseries: pd.DataFrame  # wide counts, one row per step (0..H)
    agents_start: pd.DataFrame
    agents_end: pd.DataFrame
    invariant_failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    status: str = "completed"
    elapsed_seconds: float = 0.0
    model_version: str = __version__
    created_utc: str = ""
    extinct_step: int | None = None

    @property
    def scenario(self) -> str:
        return self.config.scenario

    @property
    def seed(self) -> int:
        return int(self.config.seed)

    def shares(self) -> pd.DataFrame:
        """Wide table with share_* columns (cached; the result itself is never mutated)."""
        cached = self.__dict__.get("_shares_cache")
        if cached is None:
            cached = add_shares(self.timeseries)
            self.__dict__["_shares_cache"] = cached
        return cached

    @property
    def invariants_ok(self) -> bool:
        return not self.invariant_failures


def config_hash(config: SimulationConfig) -> str:
    return hashlib.sha256(config.to_json().encode("utf-8")).hexdigest()[:12]


def make_run_id(config: SimulationConfig) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")[:-3]
    return f"{stamp}-{config.scenario}-s{config.seed}-{config_hash(config)[:6]}"


def rng_streams(
    seed: int, dynamics_seed: int | None = None
) -> tuple[np.random.Generator, np.random.Generator, np.random.Generator]:
    """Independent streams: initialisation, dynamics, immigration.

    Separating the initialisation stream guarantees that every scenario run with the same seed
    starts from an identical population (common random numbers for the paired design).
    ``dynamics_seed`` (optional) re-seeds only the dynamics/immigration streams, so many runs can
    share one fixed initial population (used for AnyLogic docking).
    """
    init_ss, dyn_ss, imm_ss = np.random.SeedSequence(int(seed)).spawn(3)
    if dynamics_seed is not None:
        _, dyn_ss, imm_ss = np.random.SeedSequence([int(seed), int(dynamics_seed)]).spawn(3)
    return np.random.default_rng(init_ss), np.random.default_rng(dyn_ss), np.random.default_rng(imm_ss)


class Simulation:
    """Stateful engine. ``simulate()`` is the convenience wrapper for a complete run."""

    def __init__(self, config: SimulationConfig, reference: ReferenceData | None = None) -> None:
        self.config = config.validate()
        self.reference = reference or load_reference(config.reference_id)
        self.rng_init, self.rng, self.rng_imm = rng_streams(config.seed, config.dynamics_seed)
        self.init: InitializationResult = initialize_population(self.config, self.reference, self.rng_init)
        self.pop: Population = self.init.population
        self.ids = self.init.ids
        d = self.config.demography
        self.q_age = mortality_schedule(d)
        self.f_age = fertility_schedule(d)
        self.fit = FitnessArrays(self.config.selection, self.config.include_rh)
        self.capacity = self.config.carrying_capacity
        self.mutation_matrix = (
            None if self.config.mutation.matrix is None else np.array(self.config.mutation.matrix, dtype=float)
        )
        self.step_no = 0
        self.rows: list[dict] = [count_row(self.pop, 0)]
        self.invariant_failures: list[str] = []
        self.warnings: list[str] = []
        self.extinct_step: int | None = None
        self._check(self.rows[0], n_start=len(self.pop), first=True)

    # ------------------------------------------------------------------ helpers
    def _check(self, row: dict, n_start: int, first: bool = False) -> None:
        fails: list[str] = []
        t = row["step"]
        n = row["population"]
        if not first:
            expected = n_start + row["immigrants"] + row["births"] - row["deaths"] - row["emigrants"]
            if expected != n:
                fails.append(f"step {t}: accounting N_end={n} but N_start+imm+births-deaths={expected}")
            if row["deaths"] != row["deaths_natural"] + row["deaths_disease"] + row["deaths_bottleneck"]:
                fails.append(f"step {t}: death causes do not sum to total deaths")
        if sum(row[f"n_{p}"] for p in ("A", "B", "AB", "O")) != n:
            fails.append(f"step {t}: phenotype counts do not sum to N")
        if sum(row[c] for c in ("g_AA", "g_AO", "g_BB", "g_BO", "g_AB", "g_OO")) != n:
            fails.append(f"step {t}: genotype counts do not sum to N")
        if row["a_A"] + row["a_B"] + row["a_O"] != 2 * n:
            fails.append(f"step {t}: ABO allele counts do not sum to 2N")
        if row["a_D"] + row["a_d"] != 2 * n:
            fails.append(f"step {t}: RhD allele counts do not sum to 2N")
        if row["rh_pos"] + row["rh_neg"] != n:
            fails.append(f"step {t}: Rh phenotype counts do not sum to N")
        problems = self.pop.check_integrity()
        fails.extend(f"step {t}: {p}" for p in problems)
        if fails:
            self.invariant_failures.extend(fails)
            if self.config.strict_invariants:
                raise InvariantError("; ".join(fails))

    # ------------------------------------------------------------------ one year
    def step(self) -> dict:
        cfg = self.config
        d = cfg.demography
        t = self.step_no + 1
        rng = self.rng
        n_start = len(self.pop)
        ev = {k: 0 for k in ("births", "deaths", "deaths_natural", "deaths_disease", "deaths_bottleneck",
                             "immigrants", "emigrants", "fetal_losses", "mutations")}

        # 1. Immigration ------------------------------------------------------------
        for shock in cfg.shocks:
            if shock.kind == "immigration" and shock.active(t):
                newcomers = make_immigrants(shock, t, self.ids, self.rng_imm, cfg.include_rh, d.sex_ratio_female)
                self.pop = self.pop.concat(newcomers)
                ev["immigrants"] += len(newcomers)

        pop = self.pop
        n = len(pop)
        if n:
            # 2. Mortality -----------------------------------------------------------
            pheno = pop.phenotype_idx
            rhph = pop.rh_phenotype_idx
            q_nat = self.q_age[np.minimum(pop.age, d.max_age)]
            if not self.fit.survival_neutral:
                q_nat = apply_relative_risk(q_nat, self.fit.survival_rr(pheno, rhph))
            q_dis = q_nat
            for shock in cfg.shocks:
                if shock.kind == "disease" and shock.active(t):
                    q_dis = apply_disease(q_dis, shock, pheno, rhph)
            q_tot = q_dis
            for shock in cfg.shocks:
                if shock.kind == "bottleneck" and shock.active(t) and shock.fraction > 0:
                    q_tot = 1.0 - (1.0 - q_tot) * (1.0 - shock.fraction)
            u = rng.random(n)
            dead = u < q_tot
            nat = u < np.minimum(q_nat, q_dis)
            dis = dead & ~nat & (u < q_dis)
            ev["deaths"] = int(dead.sum())
            ev["deaths_natural"] = int(nat.sum())
            ev["deaths_disease"] = int(dis.sum())
            ev["deaths_bottleneck"] = ev["deaths"] - ev["deaths_natural"] - ev["deaths_disease"]
            pop = pop.subset(~dead)

            # 3. Ageing --------------------------------------------------------------
            pop.age = (pop.age + 1).astype(np.int16)

            # 4. Reproduction ----------------------------------------------------------
            newborns = self._reproduce(pop, t, ev)
            pop = pop.concat(newborns)
        self.pop = pop
        self.step_no = t

        row = count_row(self.pop, t, ev)
        self.rows.append(row)
        self._check(row, n_start=n_start)
        if len(self.pop) == 0 and self.extinct_step is None:
            self.extinct_step = t
            self.warnings.append(f"Population went extinct in year {t}.")
        return row

    def _reproduce(self, pop: Population, t: int, ev: dict) -> Population:
        cfg = self.config
        d = cfg.demography
        rng = self.rng
        fem = np.flatnonzero((pop.sex == FEMALE) & (pop.age >= d.female_min_age) & (pop.age <= d.female_max_age))
        mal = np.flatnonzero((pop.sex == MALE) & (pop.age >= d.male_min_age) & (pop.age <= d.male_max_age))
        if fem.size == 0 or mal.size == 0:
            return Population.empty()
        reg = regulation_factor(d, len(pop), self.capacity)
        pb = self.f_age[pop.age[fem]] * reg
        if not self.fit.fecundity_neutral:
            pb = pb * self.fit.fecundity(pop.phenotype_idx[fem], pop.rh_phenotype_idx[fem])
        pb = np.clip(pb, 0.0, 1.0)
        mothers = fem[rng.random(fem.size) < pb]
        k = mothers.size
        if k == 0:
            return Population.empty()
        if self.fit.fecundity_neutral:
            fathers = mal[rng.integers(0, mal.size, size=k)]
        else:
            w = self.fit.fecundity(pop.phenotype_idx[mal], pop.rh_phenotype_idx[mal])
            if w.sum() <= 0:
                return Population.empty()
            fathers = rng.choice(mal, size=k, p=w / w.sum())

        # Mendelian transmission: allele 1 from the father, allele 2 from the mother (as in the brief)
        abo_pat = transmit_alleles(pop.abo1[fathers], pop.abo2[fathers], rng)
        abo_mat = transmit_alleles(pop.abo1[mothers], pop.abo2[mothers], rng)
        if cfg.mutation.rate > 0:
            abo_pat, m1 = mutate_alleles(abo_pat, cfg.mutation.rate, rng, self.mutation_matrix)
            abo_mat, m2 = mutate_alleles(abo_mat, cfg.mutation.rate, rng, self.mutation_matrix)
            ev["mutations"] = m1 + m2
        if cfg.include_rh:
            rh_pat = transmit_alleles(pop.rh1[fathers], pop.rh2[fathers], rng)
            rh_mat = transmit_alleles(pop.rh1[mothers], pop.rh2[mothers], rng)
        else:
            rh_pat = np.zeros(k, dtype=np.int8)
            rh_mat = np.zeros(k, dtype=np.int8)

        keep = np.ones(k, dtype=bool)
        hdn = cfg.selection.hdn_loss_probability
        if cfg.include_rh and hdn > 0:
            mother_neg = pop.rh_phenotype_idx[mothers] == 1
            child_pos = (rh_pat == 0) | (rh_mat == 0)
            incompatible = mother_neg & child_pos
            at_risk = incompatible & pop.sensitized[mothers]
            lost = at_risk & (rng.random(k) < hdn)
            keep &= ~lost
            ev["fetal_losses"] = int(lost.sum())
            pop.sensitized[mothers[incompatible]] = True

        nb = int(keep.sum())
        ev["births"] = nb
        if nb == 0:
            return Population.empty()
        sex = np.where(rng.random(nb) < d.sex_ratio_female, FEMALE, MALE).astype(np.int8)
        return Population(
            agent_id=self.ids.take(nb),
            sex=sex,
            age=np.zeros(nb, dtype=np.int16),
            abo1=abo_pat[keep],
            abo2=abo_mat[keep],
            rh1=rh_pat[keep],
            rh2=rh_mat[keep],
            birth_step=np.full(nb, t, dtype=np.int32),
        )

    # ------------------------------------------------------------------ full run
    def run(self, progress: ProgressFn | None = None) -> RunResult:
        cfg = self.config
        t0 = time.perf_counter()
        agents_start = self.pop.to_frame(cfg.agent_snapshot_size, include_rh=cfg.include_rh)
        for _ in range(cfg.horizon_steps):
            self.step()
            if progress is not None:
                progress(self.step_no, cfg.horizon_steps)
        ts = pd.DataFrame(self.rows, columns=ALL_COLUMNS)
        inf = self.init.inference
        warnings = list(self.warnings)
        if self.reference.kind != "observed":
            warnings.append(f"Reference '{self.reference.title}' is {self.reference.kind}; not empirical Austria.")
        if cfg.demography.profile_id.startswith("illustrative"):
            warnings.append("Demographic profile is illustrative and uncalibrated.")
        if cfg.selection.status not in ("control",):
            warnings.append(f"Selection preset '{cfg.selection.preset}' is {cfg.selection.status}.")
        if cfg.shocks:
            warnings.append("Shock magnitudes are hypothetical scenario settings, not forecasts or medical claims.")
        return RunResult(
            run_id=make_run_id(cfg),
            config=cfg,
            config_hash=config_hash(cfg),
            reference=self.reference.metadata(),
            inference={
                "method": inf.method,
                "allele_freqs": inf.allele_freqs,
                "genotype_freqs": inf.genotype_freqs,
                "implied_phenotypes": inf.implied_phenotypes,
                "residuals": inf.residuals,
                "rh_allele_freqs": inf.rh_allele_freqs,
                "rh_genotype_freqs": inf.rh_genotype_freqs,
                "iterations": inf.iterations,
                "notes": list(inf.notes),
            },
            initial_comparison=self.init.comparison_rows(),
            timeseries=ts,
            agents_start=agents_start,
            agents_end=self.pop.to_frame(cfg.agent_snapshot_size, include_rh=cfg.include_rh),
            invariant_failures=list(self.invariant_failures),
            warnings=warnings,
            status="completed",
            elapsed_seconds=time.perf_counter() - t0,
            created_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            extinct_step=self.extinct_step,
        )


def simulate(
    config: SimulationConfig,
    reference: ReferenceData | None = None,
    progress: ProgressFn | None = None,
) -> RunResult:
    """Run one complete simulation and return an immutable result."""
    return Simulation(config, reference).run(progress)
