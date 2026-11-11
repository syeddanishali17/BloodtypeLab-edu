"""Code verification (did we implement the rules?) and run validation checks.

Nothing here returns a "pass" without actually executing the check.
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field, replace

import numpy as np
from scipy import stats

from .config import ConfigError, SimulationConfig
from .engine import RunResult, simulate
from .genetics import (
    ABO_GENOTYPES,
    canonical_genotype,
    genotype_to_codes,
    hwe_phenotype_frequencies,
    mutate_alleles,
    offspring_distribution,
    transmit_alleles,
    validate_genotype,
)
from .reference import custom_reference, infer_genotype_frequencies
from .shocks import bottleneck_shock, disease_shock, immigration_shock

ALPHA = 1e-3


@dataclass
class CheckResult:
    name: str
    category: str  # "genetics" | "accounting" | "reproducibility" | "controls" | "inference" | "science"
    passed: bool
    expected: str
    observed: str
    detail: str = ""
    seconds: float = 0.0

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class ValidationReport:
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)


# --------------------------------------------------------------------------------------
# Run-level validation
# --------------------------------------------------------------------------------------

def validate_run(run: RunResult) -> ValidationReport:
    ts = run.timeseries
    checks: list[CheckResult] = []
    n = ts["population"].to_numpy()
    expected = n[:-1] + ts["immigrants"].to_numpy()[1:] + ts["births"].to_numpy()[1:] - ts["deaths"].to_numpy()[1:] - ts["emigrants"].to_numpy()[1:]
    bad = np.flatnonzero(expected != n[1:])
    checks.append(CheckResult(
        "Population accounting every step", "accounting", bad.size == 0,
        "N_end = N_start + immigrants + births - deaths", f"{bad.size} violating steps of {len(n) - 1}",
    ))
    ph = ts[["n_A", "n_B", "n_AB", "n_O"]].sum(axis=1).to_numpy()
    ge = ts[[f"g_{g}" for g in ABO_GENOTYPES]].sum(axis=1).to_numpy()
    al = ts[["a_A", "a_B", "a_O"]].sum(axis=1).to_numpy()
    checks.append(CheckResult("Phenotype counts sum to N", "accounting", bool((ph == n).all()), "sum = N", f"max |diff| = {int(np.abs(ph - n).max())}"))
    checks.append(CheckResult("Genotype counts sum to N", "accounting", bool((ge == n).all()), "sum = N", f"max |diff| = {int(np.abs(ge - n).max())}"))
    checks.append(CheckResult("Allele counts sum to 2N", "accounting", bool((al == 2 * n).all()), "sum = 2N", f"max |diff| = {int(np.abs(al - 2 * n).max())}"))
    shares = run.shares()
    sc = [c for c in shares.columns if c.startswith("share_")]
    vals = shares[sc].to_numpy(dtype=float)
    finite = vals[np.isfinite(vals)]
    in_range = bool(((finite >= 0) & (finite <= 1)).all())
    checks.append(CheckResult("Shares within [0, 1]", "accounting", in_range, "0 <= share <= 1", f"{finite.size} values checked"))
    nonempty = n > 0
    s4 = shares.loc[nonempty, ["share_A", "share_B", "share_AB", "share_O"]].sum(axis=1).to_numpy()
    ok = bool(np.allclose(s4, 1.0, atol=1e-9)) if s4.size else True
    checks.append(CheckResult("Phenotype shares sum to 1", "accounting", ok, "1 +/- 1e-9", f"max dev = {np.abs(s4 - 1).max() if s4.size else 0:.2e}"))
    checks.append(CheckResult("Engine invariant log", "accounting", run.invariants_ok, "no failures", f"{len(run.invariant_failures)} failures"))
    return ValidationReport(checks)


# --------------------------------------------------------------------------------------
# Verification suite (executed live in the UI and by pytest)
# --------------------------------------------------------------------------------------

def _cross_check(p1: str, p2: str, n: int, rng: np.random.Generator) -> CheckResult:
    t0 = time.perf_counter()
    a1, a2 = genotype_to_codes(p1)
    b1, b2 = genotype_to_codes(p2)
    pat = transmit_alleles(np.full(n, a1, np.int8), np.full(n, a2, np.int8), rng)
    mat = transmit_alleles(np.full(n, b1, np.int8), np.full(n, b2, np.int8), rng)
    from .genetics import GENOTYPE_LUT

    counts = np.bincount(GENOTYPE_LUT[pat, mat], minlength=6)
    theory = offspring_distribution(p1, p2)
    exp = np.array([theory[g] for g in ABO_GENOTYPES]) * n
    support = exp > 0
    outside = int(counts[~support].sum())
    observed = ", ".join(f"{g} {c / n:.3f}" for g, c in zip(ABO_GENOTYPES, counts) if c)
    expected = ", ".join(f"{g} {theory[g]:.2f}" for g in ABO_GENOTYPES if theory[g])
    if support.sum() > 1:
        chi2, p = stats.chisquare(counts[support], exp[support])
        passed = outside == 0 and p > ALPHA
        detail = f"chi2 = {chi2:.2f}, p = {p:.3f} (alpha {ALPHA}), n = {n}"
    else:
        passed = outside == 0 and counts[support].sum() == n
        detail = f"deterministic cross, n = {n}"
    return CheckResult(f"Cross {p1} x {p2}", "genetics", bool(passed), expected, observed, detail, time.perf_counter() - t0)


def _timed(name: str, category: str, expected: str, fn) -> CheckResult:
    t0 = time.perf_counter()
    try:
        passed, observed, detail = fn()
    except Exception as exc:  # a crashing check is a failed check, never a silent pass
        passed, observed, detail = False, f"error: {exc!r}", ""
    return CheckResult(name, category, bool(passed), expected, observed, detail, time.perf_counter() - t0)


def run_verification_suite(n_births: int = 20_000, seed: int = 12345, quick: bool = False) -> list[CheckResult]:
    rng = np.random.default_rng(seed)
    out: list[CheckResult] = []
    for p1, p2 in (("OO", "OO"), ("AA", "OO"), ("AA", "BB"), ("AO", "OO"), ("AB", "OO"), ("AO", "BO"), ("AB", "AB")):
        out.append(_cross_check(p1, p2, n_births, rng))

    def _rh():
        pat = transmit_alleles(np.zeros(n_births, np.int8), np.ones(n_births, np.int8), rng)
        mat = transmit_alleles(np.zeros(n_births, np.int8), np.ones(n_births, np.int8), rng)
        dd = float(((pat == 1) & (mat == 1)).mean())
        z = (dd - 0.25) / np.sqrt(0.25 * 0.75 / n_births)
        return abs(z) < 3.3, f"dd share {dd:.4f}", f"z = {z:+.2f}, n = {n_births}"

    out.append(_timed("Cross Dd x Dd -> 25 % Rh-", "genetics", "dd 0.25", _rh))

    def _canon():
        ok = canonical_genotype("O", "A") == "AO" and canonical_genotype("B", "A") == "AB" and validate_genotype("OB") == "BO"
        try:
            validate_genotype("AX")
            rejected = False
        except ValueError:
            rejected = True
        return ok and rejected, f"canonical={ok}, invalid rejected={rejected}", "OA->AO, BA->AB, 'AX' -> ValueError"

    out.append(_timed("Canonical genotypes & invalid input", "genetics", "canonical + ValueError", _canon))

    def _mut0():
        a = rng.integers(0, 3, 10_000).astype(np.int8)
        b, k = mutate_alleles(a, 0.0, rng)
        return k == 0 and np.array_equal(a, b), f"{k} mutations", "rate 0"

    out.append(_timed("Mutation disabled -> no changes", "controls", "0 mutations", _mut0))

    def _hwe():
        p, q, r = 0.3, 0.1, 0.6
        ref = custom_reference(hwe_phenotype_frequencies(p, q, r), {"Rh+": 0.84, "Rh-": 0.16})
        inf = infer_genotype_frequencies(ref, "hwe_em")
        err = max(abs(inf.allele_freqs["A"] - p), abs(inf.allele_freqs["B"] - q), abs(inf.allele_freqs["O"] - r))
        d_err = abs(inf.rh_allele_freqs["d"] - 0.4)
        return err < 1e-8 and d_err < 1e-12, f"max allele error {err:.1e}; d error {d_err:.1e}", "recovers p=0.3, q=0.1, r=0.6, d=0.4"

    out.append(_timed("HWE EM recovers known allele frequencies", "inference", "error < 1e-8", _hwe))

    small = SimulationConfig(initial_population=1500 if quick else 3000, horizon_steps=40 if quick else 80, seed=seed)

    def _repro():
        r1, r2 = simulate(small), simulate(small)
        same = r1.timeseries.equals(r2.timeseries)
        return same, "identical tables" if same else "tables differ", "same config + seed twice"

    out.append(_timed("Reproducibility (same seed)", "reproducibility", "bit-identical output", _repro))

    def _seed_diff():
        r1, r2 = simulate(small), simulate(replace(small, seed=seed + 1))
        return not r1.timeseries.equals(r2.timeseries), "outputs differ", "different seeds"

    out.append(_timed("Different seeds give different runs", "reproducibility", "outputs differ", _seed_diff))

    def _zero():
        base = simulate(small)
        zero = simulate(replace(small, scenario="zero", shocks=(
            immigration_shock(count_per_step=0, start_step=10),
            disease_shock(("A", "B"), start_step=10, relative_risk=1.0),
            bottleneck_shock(fraction=0.0, start_step=20),
        )))
        same = base.timeseries.equals(zero.timeseries)
        return same, "identical to baseline" if same else "differs from baseline", "zero-magnitude shocks"

    out.append(_timed("Zero-magnitude shocks = baseline", "controls", "identical to baseline", _zero))

    def _all_shocks():
        r = simulate(replace(small, scenario="stress", mutation=replace(small.mutation, rate=0.01), shocks=(
            immigration_shock(count_per_step=300, start_step=10, duration_steps=3),
            disease_shock(("O",), start_step=15, duration_steps=5, relative_risk=5.0),
            bottleneck_shock(fraction=0.4, start_step=30),
        )))
        rep = validate_run(r)
        ts = r.timeseries
        events = f"imm {int(ts.immigrants.sum())}, disease deaths {int(ts.deaths_disease.sum())}, bottleneck deaths {int(ts.deaths_bottleneck.sum())}, mutations {int(ts.mutations.sum())}"
        ok = rep.passed and ts.immigrants.sum() == 900 and ts.deaths_disease.sum() > 0 and ts.deaths_bottleneck.sum() > 0
        return ok, events, f"{sum(c.passed for c in rep.checks)}/{len(rep.checks)} run checks passed"

    out.append(_timed("Invariants under all shocks + mutation", "accounting", "all invariants hold", _all_shocks))

    def _disease_targets():
        r = simulate(replace(small, scenario="disease", shocks=(disease_shock(("B",), start_step=5, duration_steps=10, relative_risk=8.0),)))
        s = r.shares()
        b0, b1 = s.share_B.iloc[4], s.share_B.iloc[15]
        return b1 < b0, f"share B {b0:.3f} -> {b1:.3f}", "strong B-specific disease"

    out.append(_timed("Disease reduces the targeted phenotype", "controls", "share B decreases", _disease_targets))

    def _neutral():
        n_rep = 8 if quick else 16
        deltas = []
        cfg = SimulationConfig(initial_population=1500, horizon_steps=60, seed=seed)
        for k in range(n_rep):
            s = simulate(replace(cfg, seed=seed + 100 + k)).shares()
            deltas.append(s.share_a_O.iloc[-1] - s.share_a_O.iloc[0])
        d = np.array(deltas)
        t = d.mean() / (d.std(ddof=1) / np.sqrt(len(d)))
        return abs(t) < 4, f"mean change {d.mean():+.4f} (t = {t:+.2f})", f"{n_rep} replicates, N=1500, 60 years"

    out.append(_timed("Neutral baseline has no directional trend", "science", "|t| < 4 for O-allele change", _neutral))

    def _config_rejects():
        bad = [
            dict(initial_population=1),
            dict(horizon_steps=0),
            dict(shocks=(disease_shock((), start_step=5),)),
            dict(shocks=(bottleneck_shock(fraction=1.5, start_step=5),)),
        ]
        rejected = 0
        for b in bad:
            try:
                replace(SimulationConfig(), **b).validate()
            except ConfigError:
                rejected += 1
        return rejected == len(bad), f"{rejected}/{len(bad)} rejected", "invalid configs raise ConfigError"

    out.append(_timed("Invalid configurations rejected", "controls", "all rejected", _config_rejects))
    return out
