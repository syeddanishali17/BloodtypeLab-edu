"""ABO and simplified RhD genetics.

Pure functions, no global random state, no UI imports.

Encoding used by the vectorised engine
--------------------------------------
ABO alleles:  0 = "A", 1 = "B", 2 = "O"
RhD alleles:  0 = "D" (Rh+, dominant), 1 = "d" (Rh-)

Genotype strings are canonical (alleles sorted A < B < O, D < d), e.g. "AO", never "OA".
"""
from __future__ import annotations

from itertools import product

import numpy as np

ABO_ALLELES: tuple[str, ...] = ("A", "B", "O")
RH_ALLELES: tuple[str, ...] = ("D", "d")
ABO_GENOTYPES: tuple[str, ...] = ("AA", "AO", "BB", "BO", "AB", "OO")
ABO_PHENOTYPES: tuple[str, ...] = ("A", "B", "AB", "O")
RH_GENOTYPES: tuple[str, ...] = ("DD", "Dd", "dd")
RH_PHENOTYPES: tuple[str, ...] = ("Rh+", "Rh-")
COMBINED_PHENOTYPES: tuple[str, ...] = tuple(f"{a}{r[-1]}" for a in ABO_PHENOTYPES for r in RH_PHENOTYPES)

ABO_INDEX = {a: i for i, a in enumerate(ABO_ALLELES)}
RH_INDEX = {a: i for i, a in enumerate(RH_ALLELES)}

GENOTYPE_TO_PHENOTYPE: dict[str, str] = {
    "AA": "A",
    "AO": "A",
    "BB": "B",
    "BO": "B",
    "AB": "AB",
    "OO": "O",
}
RH_GENOTYPE_TO_PHENOTYPE: dict[str, str] = {"DD": "Rh+", "Dd": "Rh+", "dd": "Rh-"}

# Lookup tables indexed by [allele_1, allele_2] (integer codes) -> category index.
GENOTYPE_LUT = np.empty((3, 3), dtype=np.int8)
PHENOTYPE_LUT = np.empty((3, 3), dtype=np.int8)
for _i, _j in product(range(3), range(3)):
    _g = "".join(sorted(ABO_ALLELES[_i] + ABO_ALLELES[_j], key=ABO_INDEX.__getitem__))
    GENOTYPE_LUT[_i, _j] = ABO_GENOTYPES.index(_g)
    PHENOTYPE_LUT[_i, _j] = ABO_PHENOTYPES.index(GENOTYPE_TO_PHENOTYPE[_g])

RH_GENOTYPE_LUT = np.array([[0, 1], [1, 2]], dtype=np.int8)
RH_PHENOTYPE_LUT = np.array([[0, 0], [0, 1]], dtype=np.int8)  # 0 = Rh+, 1 = Rh-


def _check_abo_allele(allele: str) -> str:
    if allele not in ABO_INDEX:
        raise ValueError(f"Invalid ABO allele {allele!r}; expected one of {ABO_ALLELES}")
    return allele


def _check_rh_allele(allele: str) -> str:
    if allele not in RH_INDEX:
        raise ValueError(f"Invalid RhD allele {allele!r}; expected one of {RH_ALLELES}")
    return allele


def canonical_genotype(allele_1: str, allele_2: str) -> str:
    """Return the unordered canonical ABO genotype string (``"OA"`` -> ``"AO"``)."""
    a, b = _check_abo_allele(allele_1), _check_abo_allele(allele_2)
    return "".join(sorted(a + b, key=ABO_INDEX.__getitem__))


def canonical_rh_genotype(allele_1: str, allele_2: str) -> str:
    a, b = _check_rh_allele(allele_1), _check_rh_allele(allele_2)
    return "".join(sorted(a + b, key=RH_INDEX.__getitem__))


def validate_genotype(genotype: str) -> str:
    """Validate and canonicalise an ABO genotype string such as ``"OA"``."""
    if not isinstance(genotype, str) or len(genotype) != 2:
        raise ValueError(f"Invalid ABO genotype {genotype!r}: must be two alleles from {ABO_ALLELES}")
    return canonical_genotype(genotype[0], genotype[1])


def validate_rh_genotype(genotype: str) -> str:
    if not isinstance(genotype, str) or len(genotype) != 2:
        raise ValueError(f"Invalid RhD genotype {genotype!r}: must be two alleles from {RH_ALLELES}")
    return canonical_rh_genotype(genotype[0], genotype[1])


def phenotype_from_genotype(genotype: str) -> str:
    """ABO phenotype of a genotype (A and B codominant, O recessive)."""
    return GENOTYPE_TO_PHENOTYPE[validate_genotype(genotype)]


def rh_phenotype_from_genotype(genotype: str) -> str:
    return RH_GENOTYPE_TO_PHENOTYPE[validate_rh_genotype(genotype)]


def inherit_genotype(parent_1: str, parent_2: str, rng: np.random.Generator) -> str:
    """Draw one child ABO genotype: one random allele from each parent (Mendel's first law)."""
    p1, p2 = validate_genotype(parent_1), validate_genotype(parent_2)
    return canonical_genotype(p1[rng.integers(2)], p2[rng.integers(2)])


def inherit_rh_genotype(parent_1: str, parent_2: str, rng: np.random.Generator) -> str:
    p1, p2 = validate_rh_genotype(parent_1), validate_rh_genotype(parent_2)
    return canonical_rh_genotype(p1[rng.integers(2)], p2[rng.integers(2)])


def offspring_distribution(parent_1: str, parent_2: str) -> dict[str, float]:
    """Exact theoretical offspring ABO genotype distribution (Punnett square)."""
    p1, p2 = validate_genotype(parent_1), validate_genotype(parent_2)
    out = {g: 0.0 for g in ABO_GENOTYPES}
    for a, b in product(p1, p2):
        out[canonical_genotype(a, b)] += 0.25
    return out


def offspring_phenotype_distribution(parent_1: str, parent_2: str) -> dict[str, float]:
    out = {p: 0.0 for p in ABO_PHENOTYPES}
    for g, prob in offspring_distribution(parent_1, parent_2).items():
        out[GENOTYPE_TO_PHENOTYPE[g]] += prob
    return out


def punnett_square(parent_1: str, parent_2: str) -> list[list[str]]:
    """2x2 Punnett square: rows = alleles of parent_1, columns = alleles of parent_2."""
    p1, p2 = validate_genotype(parent_1), validate_genotype(parent_2)
    return [[canonical_genotype(a, b) for b in p2] for a in p1]


def transmission_labels(genotype: str, role: str) -> list[str]:
    """Axis labels for one parent. Allele 1 and allele 2 stay distinct for AA, BB and OO."""
    g = validate_genotype(genotype)
    return [f"{role} allele {i} ({allele})" for i, allele in enumerate(g, start=1)]


def genotype_to_codes(genotype: str) -> tuple[int, int]:
    g = validate_genotype(genotype)
    return ABO_INDEX[g[0]], ABO_INDEX[g[1]]


# --------------------------------------------------------------------------------------
# Vectorised operators used by the engine
# --------------------------------------------------------------------------------------

def transmit_alleles(allele_1: np.ndarray, allele_2: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Pick one allele per parent uniformly at random (vectorised)."""
    pick_second = rng.random(allele_1.shape[0]) < 0.5
    return np.where(pick_second, allele_2, allele_1)


def default_mutation_matrix() -> np.ndarray:
    """Row-stochastic matrix: conditional on mutating, move uniformly to one of the other two alleles."""
    m = np.full((3, 3), 0.5)
    np.fill_diagonal(m, 0.0)
    return m


def mutate_alleles(
    alleles: np.ndarray,
    rate: float,
    rng: np.random.Generator,
    matrix: np.ndarray | None = None,
) -> tuple[np.ndarray, int]:
    """Apply per-transmission mutation with probability ``rate``.

    Returns (new_alleles, number_of_mutations). With ``rate == 0`` no random numbers are
    consumed, so zero-rate runs are bit-identical to runs without the mutation module.
    """
    if rate <= 0 or alleles.size == 0:
        return alleles, 0
    if not 0 <= rate <= 1:
        raise ValueError("mutation rate must be in [0, 1]")
    matrix = default_mutation_matrix() if matrix is None else np.asarray(matrix, dtype=float)
    mutate = rng.random(alleles.shape[0]) < rate
    n = int(mutate.sum())
    if n == 0:
        return alleles, 0
    out = alleles.copy()
    src = alleles[mutate]
    cum = np.cumsum(matrix[src], axis=1)
    u = rng.random(n)[:, None]
    out[mutate] = (u > cum).sum(axis=1).clip(0, 2).astype(alleles.dtype)
    return out, n


def hwe_genotype_frequencies(p_a: float, p_b: float, p_o: float) -> dict[str, float]:
    """Hardy-Weinberg genotype frequencies from allele frequencies."""
    return {
        "AA": p_a * p_a,
        "AO": 2 * p_a * p_o,
        "BB": p_b * p_b,
        "BO": 2 * p_b * p_o,
        "AB": 2 * p_a * p_b,
        "OO": p_o * p_o,
    }


def hwe_phenotype_frequencies(p_a: float, p_b: float, p_o: float) -> dict[str, float]:
    g = hwe_genotype_frequencies(p_a, p_b, p_o)
    return {"A": g["AA"] + g["AO"], "B": g["BB"] + g["BO"], "AB": g["AB"], "O": g["OO"]}
