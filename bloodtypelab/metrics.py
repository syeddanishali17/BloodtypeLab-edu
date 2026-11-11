"""Per-step population metrics and long-format result tables."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .agents import FEMALE, Population
from .genetics import (
    ABO_ALLELES,
    ABO_GENOTYPES,
    ABO_PHENOTYPES,
    COMBINED_PHENOTYPES,
    RH_ALLELES,
    RH_PHENOTYPES,
)

EVENT_COLUMNS = [
    "births",
    "deaths",
    "deaths_natural",
    "deaths_disease",
    "deaths_bottleneck",
    "immigrants",
    "emigrants",
    "fetal_losses",
    "mutations",
]
PHENO_COLS = [f"n_{p}" for p in ABO_PHENOTYPES]
GENO_COLS = [f"g_{g}" for g in ABO_GENOTYPES]
ALLELE_COLS = [f"a_{a}" for a in ABO_ALLELES]
RH_COLS = ["rh_pos", "rh_neg"]
RH_ALLELE_COLS = [f"a_{a}" for a in RH_ALLELES]  # a_D, a_d
COMBINED_COLS = [f"bt_{c}" for c in COMBINED_PHENOTYPES]
ALL_COLUMNS = (
    ["step", "population"]
    + EVENT_COLUMNS
    + ["n_female", "mean_age", "het_obs", "het_exp"]
    + PHENO_COLS
    + GENO_COLS
    + ALLELE_COLS
    + RH_COLS
    + RH_ALLELE_COLS
    + COMBINED_COLS
)

# Share columns derived from counts: name -> (count column, denominator: "N" or "2N")
SHARE_SPECS: dict[str, tuple[str, str]] = {}
for _p in ABO_PHENOTYPES:
    SHARE_SPECS[f"share_{_p}"] = (f"n_{_p}", "N")
for _g in ABO_GENOTYPES:
    SHARE_SPECS[f"share_g_{_g}"] = (f"g_{_g}", "N")
for _a in ABO_ALLELES:
    SHARE_SPECS[f"share_a_{_a}"] = (f"a_{_a}", "2N")
SHARE_SPECS["share_rh_pos"] = ("rh_pos", "N")
SHARE_SPECS["share_rh_neg"] = ("rh_neg", "N")
for _a in RH_ALLELES:
    SHARE_SPECS[f"share_a_{_a}"] = (f"a_{_a}", "2N")
for _c in COMBINED_PHENOTYPES:
    SHARE_SPECS[f"share_bt_{_c}"] = (f"bt_{_c}", "N")


def count_row(pop: Population, step: int, events: dict[str, int] | None = None) -> dict[str, float]:
    """Counts describing ``pop`` at the end of ``step``."""
    n = len(pop)
    row: dict[str, float] = {"step": step, "population": n}
    events = events or {}
    for c in EVENT_COLUMNS:
        row[c] = int(events.get(c, 0))
    row["n_female"] = int((pop.sex == FEMALE).sum()) if n else 0
    row["mean_age"] = float(pop.age.mean()) if n else float("nan")

    ph = np.bincount(pop.phenotype_idx, minlength=4) if n else np.zeros(4, int)
    gi = pop.genotype_idx
    ge = np.bincount(gi, minlength=6) if n else np.zeros(6, int)
    al = (np.bincount(pop.abo1, minlength=3) + np.bincount(pop.abo2, minlength=3)) if n else np.zeros(3, int)
    rph = pop.rh_phenotype_idx
    rp = np.bincount(rph, minlength=2) if n else np.zeros(2, int)
    ra = (np.bincount(pop.rh1, minlength=2) + np.bincount(pop.rh2, minlength=2)) if n else np.zeros(2, int)
    comb = np.bincount(pop.phenotype_idx * 2 + rph, minlength=8) if n else np.zeros(8, int)

    for i, c in enumerate(PHENO_COLS):
        row[c] = int(ph[i])
    for i, c in enumerate(GENO_COLS):
        row[c] = int(ge[i])
    for i, c in enumerate(ALLELE_COLS):
        row[c] = int(al[i])
    row["rh_pos"], row["rh_neg"] = int(rp[0]), int(rp[1])
    for i, c in enumerate(RH_ALLELE_COLS):
        row[c] = int(ra[i])
    for i, c in enumerate(COMBINED_COLS):
        row[c] = int(comb[i])

    if n:
        hets = ge[ABO_GENOTYPES.index("AO")] + ge[ABO_GENOTYPES.index("BO")] + ge[ABO_GENOTYPES.index("AB")]
        row["het_obs"] = float(hets / n)
        p = al / (2 * n)
        row["het_exp"] = float(1 - (p**2).sum())
    else:
        row["het_obs"] = row["het_exp"] = float("nan")
    return row


def population_shares(pop: Population) -> dict[str, dict[str, float]]:
    row = count_row(pop, 0)
    n = max(len(pop), 1)
    return {
        "phenotype": {p: row[f"n_{p}"] / n for p in ABO_PHENOTYPES},
        "genotype": {g: row[f"g_{g}"] / n for g in ABO_GENOTYPES},
        "allele": {a: row[f"a_{a}"] / (2 * n) for a in ABO_ALLELES},
        "rh": {"Rh+": row["rh_pos"] / n, "Rh-": row["rh_neg"] / n},
        "rh_allele": {a: row[f"a_{a}"] / (2 * n) for a in RH_ALLELES},
        "combined": {c: row[f"bt_{c}"] / n for c in COMBINED_PHENOTYPES},
    }


def add_shares(ts: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of a wide count table with share_* columns (fractions; NaN if N = 0)."""
    out = ts.copy()
    n = out["population"].astype(float).replace(0, np.nan)
    for name, (col, denom) in SHARE_SPECS.items():
        out[name] = out[col] / (n if denom == "N" else 2 * n)
    return out


def long_table(ts: pd.DataFrame, kind: str, run_id: str, scenario: str, seed: int) -> pd.DataFrame:
    """Long-format export table (count + share fraction) for phenotype/genotype/allele/rh."""
    if kind == "phenotype":
        cats, cols, label, denom = ABO_PHENOTYPES, PHENO_COLS, "phenotype", 1
    elif kind == "genotype":
        cats, cols, label, denom = ABO_GENOTYPES, GENO_COLS, "genotype", 1
    elif kind == "allele":
        cats, cols, label, denom = ABO_ALLELES + RH_ALLELES, ALLELE_COLS + RH_ALLELE_COLS, "allele", 2
    elif kind == "rh":
        cats, cols, label, denom = RH_PHENOTYPES, RH_COLS, "rh_phenotype", 1
    elif kind == "blood_type":
        cats, cols, label, denom = COMBINED_PHENOTYPES, COMBINED_COLS, "blood_type", 1
    else:
        raise ValueError(kind)
    frames = []
    n = ts["population"].astype(float).replace(0, np.nan) * denom
    for cat, col in zip(cats, cols):
        frames.append(
            pd.DataFrame(
                {
                    "run_id": run_id,
                    "scenario": scenario,
                    "seed": seed,
                    "step": ts["step"].values,
                    label: cat,
                    "count": ts[col].values,
                    "share": (ts[col] / n).values,
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def population_table(ts: pd.DataFrame, run_id: str, scenario: str, seed: int) -> pd.DataFrame:
    cols = ["step", "population"] + EVENT_COLUMNS + ["n_female", "mean_age", "het_obs", "het_exp"]
    df = ts[cols].copy()
    df.insert(0, "seed", seed)
    df.insert(0, "scenario", scenario)
    df.insert(0, "run_id", run_id)
    return df
