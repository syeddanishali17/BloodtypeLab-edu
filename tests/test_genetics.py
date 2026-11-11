import numpy as np
import pytest
from scipy import stats

from bloodtypelab.genetics import (
    ABO_GENOTYPES,
    GENOTYPE_LUT,
    canonical_genotype,
    genotype_to_codes,
    inherit_genotype,
    mutate_alleles,
    offspring_distribution,
    offspring_phenotype_distribution,
    phenotype_from_genotype,
    punnett_square,
    transmission_labels,
    rh_phenotype_from_genotype,
    transmit_alleles,
    validate_genotype,
)


@pytest.mark.parametrize(
    "g,p",
    [("AA", "A"), ("AO", "A"), ("OA", "A"), ("BB", "B"), ("BO", "B"), ("AB", "AB"), ("BA", "AB"), ("OO", "O")],
)
def test_phenotype_mapping(g, p):
    assert phenotype_from_genotype(g) == p


def test_six_canonical_genotypes():
    seen = {canonical_genotype(a, b) for a in "ABO" for b in "ABO"}
    assert seen == set(ABO_GENOTYPES)
    assert canonical_genotype("O", "A") == "AO"


@pytest.mark.parametrize("bad", ["AX", "A", "", "ABO", "ao", None])
def test_invalid_genotypes_rejected(bad):
    with pytest.raises(ValueError):
        validate_genotype(bad)


def test_rh_phenotypes():
    assert rh_phenotype_from_genotype("DD") == "Rh+"
    assert rh_phenotype_from_genotype("dD") == "Rh+"
    assert rh_phenotype_from_genotype("dd") == "Rh-"


@pytest.mark.parametrize("genotype", ["AA", "BB", "OO", "AO", "BO", "AB"])
def test_transmission_labels_stay_unique(genotype):
    labels = transmission_labels(genotype, "Mother")
    assert len(labels) == 2
    assert len(set(labels)) == 2
    assert labels[0] != labels[1]


def test_homozygote_punnett_frame_has_unique_columns():
    """st.table sends the frame through PyArrow, which rejects duplicate column names."""
    pa = pytest.importorskip("pyarrow")
    pd = pytest.importorskip("pandas")
    for father in ABO_GENOTYPES:
        for mother in ABO_GENOTYPES:
            square = punnett_square(father, mother)
            frame = pd.DataFrame(
                square,
                index=transmission_labels(father, "Father"),
                columns=transmission_labels(mother, "Mother"),
            )
            pa.Table.from_pandas(frame)


def test_punnett_square_ao_bo():
    assert punnett_square("AO", "BO") == [["AB", "AO"], ["BO", "OO"]]
    d = offspring_distribution("AO", "BO")
    assert d["AB"] == d["AO"] == d["BO"] == d["OO"] == 0.25
    assert offspring_phenotype_distribution("AO", "BO") == {"A": 0.25, "B": 0.25, "AB": 0.25, "O": 0.25}


@pytest.mark.parametrize("p1,p2,child", [("OO", "OO", "OO"), ("AA", "OO", "AO"), ("AA", "BB", "AB")])
def test_deterministic_crosses(p1, p2, child):
    rng = np.random.default_rng(1)
    assert {inherit_genotype(p1, p2, rng) for _ in range(500)} == {child}


@pytest.mark.parametrize("p1,p2", [("AO", "OO"), ("AB", "OO"), ("AO", "BO"), ("AB", "AB"), ("AO", "AO")])
def test_stochastic_crosses_chi_square(p1, p2):
    rng = np.random.default_rng(7)
    n = 20_000
    a1, a2 = genotype_to_codes(p1)
    b1, b2 = genotype_to_codes(p2)
    pat = transmit_alleles(np.full(n, a1, np.int8), np.full(n, a2, np.int8), rng)
    mat = transmit_alleles(np.full(n, b1, np.int8), np.full(n, b2, np.int8), rng)
    counts = np.bincount(GENOTYPE_LUT[pat, mat], minlength=6)
    theory = offspring_distribution(p1, p2)
    exp = np.array([theory[g] for g in ABO_GENOTYPES]) * n
    support = exp > 0
    assert counts[~support].sum() == 0  # no impossible children
    _, pval = stats.chisquare(counts[support], exp[support])
    assert pval > 1e-3


def test_scalar_inheritance_matches_theory():
    rng = np.random.default_rng(3)
    kids = [inherit_genotype("AO", "BO", rng) for _ in range(8000)]
    for g in ("AB", "AO", "BO", "OO"):
        assert abs(kids.count(g) / 8000 - 0.25) < 0.02


def test_mutation_zero_rate_is_identity_and_consumes_no_randomness():
    rng = np.random.default_rng(0)
    a = np.array([0, 1, 2, 2, 1], dtype=np.int8)
    state = rng.bit_generator.state
    b, k = mutate_alleles(a, 0.0, rng)
    assert k == 0 and np.array_equal(a, b)
    assert rng.bit_generator.state == state


def test_mutation_full_rate_always_changes_allele():
    rng = np.random.default_rng(0)
    a = rng.integers(0, 3, 5000).astype(np.int8)
    b, k = mutate_alleles(a, 1.0, rng)
    assert k == 5000 and np.all(a != b) and b.min() >= 0 and b.max() <= 2
