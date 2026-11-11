"""Synthetic initial population built from a reference dataset."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .agents import FEMALE, MALE, IdAllocator, Population
from .config import SimulationConfig
from .demography import stationary_age_distribution
from .genetics import ABO_GENOTYPES, ABO_INDEX, RH_GENOTYPES, RH_INDEX
from .metrics import population_shares
from .reference import InferenceResult, ReferenceData, infer_genotype_frequencies


@dataclass
class InitializationResult:
    population: Population
    ids: IdAllocator
    inference: InferenceResult
    target_phenotypes: dict[str, float]
    target_rh: dict[str, float]
    realised: dict[str, dict[str, float]]

    def comparison_rows(self) -> list[dict]:
        rows = []
        for k, v in self.target_phenotypes.items():
            rows.append(
                {
                    "category": k,
                    "target_reference": v,
                    "inferred_hwe": self.inference.implied_phenotypes[k],
                    "realised_initial": self.realised["phenotype"][k],
                }
            )
        for k, v in self.target_rh.items():
            rows.append({"category": k, "target_reference": v, "inferred_hwe": v, "realised_initial": self.realised["rh"][k]})
        return rows


def allocate_counts(freqs: np.ndarray, n: int, rng: np.random.Generator, method: str) -> np.ndarray:
    """Split n agents into categories: multinomial sampling or deterministic largest-remainder quota."""
    freqs = np.asarray(freqs, dtype=float)
    freqs = freqs / freqs.sum()
    if method == "multinomial":
        return rng.multinomial(n, freqs)
    if method == "quota":
        raw = freqs * n
        counts = np.floor(raw).astype(int)
        rem = n - counts.sum()
        order = np.argsort(-(raw - counts), kind="stable")
        counts[order[:rem]] += 1
        return counts
    raise ValueError(f"Unknown allocation {method!r}")


def _alleles_from_genotype_counts(
    counts: np.ndarray, genotypes: tuple[str, ...], index: dict[str, int], rng: np.random.Generator
) -> tuple[np.ndarray, np.ndarray]:
    a1 = np.concatenate([np.full(c, index[g[0]], dtype=np.int8) for g, c in zip(genotypes, counts)])
    a2 = np.concatenate([np.full(c, index[g[1]], dtype=np.int8) for g, c in zip(genotypes, counts)])
    # Parent-of-origin order is unknown for founders: randomise it for heterozygotes.
    swap = rng.random(a1.shape[0]) < 0.5
    a1s = np.where(swap, a2, a1)
    a2s = np.where(swap, a1, a2)
    return a1s, a2s


def sample_agents(
    n: int,
    genotype_freqs: dict[str, float],
    rh_genotype_freqs: dict[str, float] | None,
    age_weights: np.ndarray,
    sex_ratio_female: float,
    ids: IdAllocator,
    step: int,
    rng: np.random.Generator,
    allocation: str = "multinomial",
    age_values: np.ndarray | None = None,
) -> Population:
    """Create ``n`` agents with genotypes, RhD, sex and ages drawn as specified."""
    if n == 0:
        return Population.empty()
    g_counts = allocate_counts(np.array([genotype_freqs[g] for g in ABO_GENOTYPES]), n, rng, allocation)
    abo1, abo2 = _alleles_from_genotype_counts(g_counts, ABO_GENOTYPES, ABO_INDEX, rng)
    if rh_genotype_freqs is not None:
        r_counts = allocate_counts(np.array([rh_genotype_freqs[g] for g in RH_GENOTYPES]), n, rng, allocation)
        rh1, rh2 = _alleles_from_genotype_counts(r_counts, RH_GENOTYPES, RH_INDEX, rng)
        # Independent loci: shuffle Rh relative to ABO
        perm = rng.permutation(n)
        rh1, rh2 = rh1[perm], rh2[perm]
    else:
        rh1 = np.zeros(n, dtype=np.int8)
        rh2 = np.zeros(n, dtype=np.int8)
    order = rng.permutation(n)
    abo1, abo2, rh1, rh2 = abo1[order], abo2[order], rh1[order], rh2[order]
    sex = np.where(rng.random(n) < sex_ratio_female, FEMALE, MALE).astype(np.int8)
    values = np.arange(age_weights.shape[0]) if age_values is None else age_values
    age = rng.choice(values, size=n, p=age_weights / age_weights.sum()).astype(np.int16)
    return Population(
        agent_id=ids.take(n),
        sex=sex,
        age=age,
        abo1=abo1,
        abo2=abo2,
        rh1=rh1,
        rh2=rh2,
        birth_step=(step - age).astype(np.int32),
    )


def initialize_population(
    config: SimulationConfig, reference: ReferenceData, rng: np.random.Generator
) -> InitializationResult:
    inference = infer_genotype_frequencies(
        reference,
        config.initialization_method,
        aa_fraction=config.explicit_split_aa_fraction,
        bb_fraction=config.explicit_split_bb_fraction,
    )
    ids = IdAllocator()
    pop = sample_agents(
        n=config.initial_population,
        genotype_freqs=inference.genotype_freqs,
        rh_genotype_freqs=inference.rh_genotype_freqs if config.include_rh else None,
        age_weights=stationary_age_distribution(config.demography),
        sex_ratio_female=config.demography.sex_ratio_female,
        ids=ids,
        step=0,
        rng=rng,
        allocation=config.allocation,
    )
    realised = population_shares(pop)
    return InitializationResult(
        population=pop,
        ids=ids,
        inference=inference,
        target_phenotypes=dict(reference.abo),
        target_rh=dict(reference.rh),
        realised=realised,
    )
