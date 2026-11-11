"""External shocks: immigration, phenotype-dependent disease, neutral bottleneck.

All shock magnitudes are HYPOTHETICAL scenario settings; no medical claims are made.
"""
from __future__ import annotations

import numpy as np

from .agents import IdAllocator, Population
from .config import ShockConfig
from .genetics import ABO_PHENOTYPES, RH_PHENOTYPES, hwe_genotype_frequencies
from .initialization import sample_agents
from .selection import apply_relative_risk

IMMIGRATION_SOURCES: dict[str, dict] = {
    "same_as_residents": {
        "title": "Same as residents (Austria HWE)",
        "allele_freqs": {"A": 0.28, "B": 0.11, "O": 0.61},
        "rh_neg_allele": 0.44,
        "status": "control - matches resident inference (approximately)",
    },
    "high_b_source": {
        "title": "High-B source (hypothetical)",
        "allele_freqs": {"A": 0.20, "B": 0.25, "O": 0.55},
        "rh_neg_allele": 0.25,
        "status": "hypothetical",
    },
    "high_o_source": {
        "title": "High-O source (hypothetical)",
        "allele_freqs": {"A": 0.12, "B": 0.08, "O": 0.80},
        "rh_neg_allele": 0.20,
        "status": "hypothetical",
    },
    "high_a_source": {
        "title": "High-A source (hypothetical)",
        "allele_freqs": {"A": 0.40, "B": 0.08, "O": 0.52},
        "rh_neg_allele": 0.45,
        "status": "hypothetical",
    },
}


def immigration_shock(source: str = "high_b_source", start_step: int = 50, count_per_step: int = 500,
                      duration_steps: int = 1, age_min: int = 18, age_max: int = 40) -> ShockConfig:
    src = IMMIGRATION_SOURCES[source]
    return ShockConfig(
        kind="immigration",
        start_step=start_step,
        duration_steps=duration_steps,
        count_per_step=count_per_step,
        source_allele_freqs=dict(src["allele_freqs"]),
        source_rh_neg_allele_freq=src["rh_neg_allele"],
        source_name=src["title"],
        age_min=age_min,
        age_max=age_max,
    )


def disease_shock(affected: tuple[str, ...] = ("A",), start_step: int = 50, duration_steps: int = 5,
                  relative_risk: float = 3.0, mode: str = "relative_risk", additional_probability: float = 0.0,
                  affected_rh: tuple[str, ...] = ()) -> ShockConfig:
    return ShockConfig(
        kind="disease",
        start_step=start_step,
        duration_steps=duration_steps,
        affected_phenotypes=tuple(affected),
        affected_rh=tuple(affected_rh),
        mode=mode,  # type: ignore[arg-type]
        relative_risk=relative_risk,
        additional_probability=additional_probability,
    )


def bottleneck_shock(fraction: float = 0.5, start_step: int = 50) -> ShockConfig:
    return ShockConfig(kind="bottleneck", start_step=start_step, duration_steps=1, fraction=fraction)


# --------------------------------------------------------------------------------------
# Engine hooks
# --------------------------------------------------------------------------------------

def make_immigrants(
    shock: ShockConfig,
    step: int,
    ids: IdAllocator,
    rng: np.random.Generator,
    include_rh: bool,
    sex_ratio_female: float,
) -> Population:
    n = int(shock.count_per_step)
    if n <= 0:
        return Population.empty()
    f = shock.source_allele_freqs
    g = hwe_genotype_frequencies(f["A"], f["B"], f["O"])
    d = shock.source_rh_neg_allele_freq
    rh_g = {"DD": (1 - d) ** 2, "Dd": 2 * d * (1 - d), "dd": d * d} if include_rh else None
    ages = np.arange(shock.age_min, shock.age_max + 1)
    return sample_agents(
        n=n,
        genotype_freqs=g,
        rh_genotype_freqs=rh_g,
        age_weights=np.ones(ages.shape[0]),
        sex_ratio_female=sex_ratio_female,
        ids=ids,
        step=step,
        rng=rng,
        allocation="multinomial",
        age_values=ages,
    )


def disease_mask(shock: ShockConfig, pheno_idx: np.ndarray, rh_idx: np.ndarray) -> np.ndarray:
    affected = np.isin(pheno_idx, [ABO_PHENOTYPES.index(p) for p in shock.affected_phenotypes])
    if shock.affected_rh:
        affected &= np.isin(rh_idx, [RH_PHENOTYPES.index(r) for r in shock.affected_rh])
    return affected


def apply_disease(q: np.ndarray, shock: ShockConfig, pheno_idx: np.ndarray, rh_idx: np.ndarray) -> np.ndarray:
    """Return the death probability after the disease effect (one combined probability per agent)."""
    mask = disease_mask(shock, pheno_idx, rh_idx)
    if not mask.any():
        return q
    out = q.copy()
    if shock.mode == "relative_risk":
        if shock.relative_risk == 1.0:
            return q
        rr = np.where(mask, shock.relative_risk, 1.0)
        return apply_relative_risk(q, rr)
    extra = shock.additional_probability
    if extra == 0.0:
        return q
    out[mask] = 1.0 - (1.0 - q[mask]) * (1.0 - extra)
    return out
