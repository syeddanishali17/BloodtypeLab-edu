import numpy as np
import pytest

from bloodtypelab.config import SimulationConfig
from bloodtypelab.engine import rng_streams
from bloodtypelab.genetics import hwe_phenotype_frequencies
from bloodtypelab.initialization import allocate_counts, initialize_population
from bloodtypelab.reference import ReferenceError_, custom_reference, infer_genotype_frequencies, load_reference


def test_austria_reference_loads_and_sums_to_one():
    ref = load_reference("austria_gesundheitsportal_2022")
    assert ref.kind == "observed"
    assert ref.abo == pytest.approx({"A": 0.41, "B": 0.15, "AB": 0.07, "O": 0.37})
    assert ref.rh == pytest.approx({"Rh+": 0.81, "Rh-": 0.19})
    assert ref.file_sha256 and "gesundheit.gv.at" in ref.source_url


def test_synthetic_reference_is_labelled():
    ref = load_reference("synthetic_demo")
    assert ref.kind == "synthetic" and "NOT Austria" in ref.title


def test_invalid_reference_rejected():
    with pytest.raises(ReferenceError_):
        custom_reference({"A": 0.5, "B": 0.5, "AB": 0.5, "O": 0.0}, {"Rh+": 0.8, "Rh-": 0.2})
    with pytest.raises(ReferenceError_):
        load_reference("no_such_reference")


@pytest.mark.parametrize("method", ["hwe_em", "hwe_bernstein"])
def test_hwe_inference_recovers_known_frequencies(method):
    p, q, r = 0.25, 0.15, 0.60
    ref = custom_reference(hwe_phenotype_frequencies(p, q, r), {"Rh+": 0.84, "Rh-": 0.16})
    inf = infer_genotype_frequencies(ref, method)
    assert inf.allele_freqs["A"] == pytest.approx(p, abs=1e-6)
    assert inf.allele_freqs["B"] == pytest.approx(q, abs=1e-6)
    assert inf.allele_freqs["O"] == pytest.approx(r, abs=1e-6)
    assert inf.max_abs_residual < 1e-6
    assert inf.rh_allele_freqs["d"] == pytest.approx(0.4)


def test_austria_em_residuals_reported_and_small():
    inf = infer_genotype_frequencies(load_reference("austria_gesundheitsportal_2022"), "hwe_em")
    assert sum(inf.genotype_freqs.values()) == pytest.approx(1.0)
    assert 0 < inf.max_abs_residual < 0.01  # rounded data are not exactly in HWE: residual is reported
    assert inf.allele_freqs["O"] == pytest.approx(0.605, abs=0.005)


def test_explicit_split_is_exact():
    ref = load_reference("austria_gesundheitsportal_2022")
    inf = infer_genotype_frequencies(ref, "explicit_split", aa_fraction=0.2, bb_fraction=0.1)
    assert inf.max_abs_residual < 1e-12
    assert inf.genotype_freqs["AA"] == pytest.approx(0.41 * 0.2)


def test_quota_allocation_exact_counts():
    counts = allocate_counts(np.array([0.41, 0.15, 0.07, 0.37]), 1000, np.random.default_rng(0), "quota")
    assert counts.tolist() == [410, 150, 70, 370]


def test_initial_population_matches_targets_and_is_reproducible():
    cfg = SimulationConfig(initial_population=20_000, seed=5)
    ref = load_reference(cfg.reference_id)
    a = initialize_population(cfg, ref, rng_streams(5)[0])
    b = initialize_population(cfg, ref, rng_streams(5)[0])
    assert np.array_equal(a.population.abo1, b.population.abo1)
    assert np.array_equal(a.population.age, b.population.age)
    for k, v in a.inference.implied_phenotypes.items():
        assert abs(a.realised["phenotype"][k] - v) < 0.015
    assert abs(a.realised["rh"]["Rh-"] - 0.19) < 0.015
    assert len(a.population) == 20_000
    assert a.population.check_integrity() == []
