from dataclasses import replace

import numpy as np
import pytest

from bloodtypelab.config import ConfigError, DemographyConfig, MutationConfig, SimulationConfig
from bloodtypelab.demography import fertility_schedule, life_expectancy, mortality_schedule
from bloodtypelab.engine import Simulation, simulate
from bloodtypelab.selection import preset
from bloodtypelab.shocks import bottleneck_shock, disease_shock, immigration_shock
from bloodtypelab.validation import validate_run

SMALL = SimulationConfig(initial_population=2000, horizon_steps=60, seed=11)


def test_demography_schedules_are_valid_probabilities():
    d = DemographyConfig()
    q, f = mortality_schedule(d), fertility_schedule(d)
    assert np.all((q >= 0) & (q <= 1)) and q[-1] == 1.0
    assert np.all((f >= 0) & (f <= 1)) and f.sum() == pytest.approx(d.tfr)
    assert 75 < life_expectancy(d) < 85


def test_baseline_invariants_every_step():
    run = simulate(SMALL)
    assert run.invariants_ok
    assert validate_run(run).passed
    assert len(run.timeseries) == SMALL.horizon_steps + 1
    assert run.timeseries.immigrants.sum() == 0
    assert run.timeseries.deaths_disease.sum() == 0 and run.timeseries.deaths_bottleneck.sum() == 0


def test_population_roughly_stable_with_regulation():
    run = simulate(replace(SMALL, horizon_steps=150))
    n = run.timeseries.population
    assert 0.75 * n.iloc[0] < n.iloc[-1] < 1.3 * n.iloc[0]


def test_reproducible_and_seed_sensitive():
    a, b = simulate(SMALL), simulate(SMALL)
    assert a.timeseries.equals(b.timeseries)
    c = simulate(replace(SMALL, seed=12))
    assert not a.timeseries.equals(c.timeseries)


def test_same_seed_same_initial_population_across_scenarios():
    a = simulate(SMALL)
    b = simulate(replace(SMALL, scenario="imm", shocks=(immigration_shock(count_per_step=500, start_step=10),)))
    assert a.timeseries.iloc[:10].equals(b.timeseries.iloc[:10])
    assert a.agents_start.equals(b.agents_start)


def test_no_birth_from_dead_or_ineligible_parent_and_newborns_age_zero():
    sim = Simulation(SMALL)
    for _ in range(5):
        before_ids = set(sim.pop.agent_id.tolist())
        sim.step()
        new = sim.pop.birth_step == sim.step_no
        assert np.all(sim.pop.age[new] == 0)
        assert not (set(sim.pop.agent_id[new].tolist()) & before_ids)


def test_zero_fertility_gives_no_births():
    cfg = replace(SMALL, demography=replace(SMALL.demography, tfr=0.0))
    run = simulate(cfg)
    assert run.timeseries.births.sum() == 0
    assert run.timeseries.population.iloc[-1] < SMALL.initial_population


def test_extinction_is_handled():
    cfg = replace(SMALL, initial_population=50, horizon_steps=30,
                  shocks=(bottleneck_shock(fraction=1.0, start_step=5),))
    run = simulate(cfg)
    assert run.extinct_step == 5
    assert run.timeseries.population.iloc[-1] == 0
    assert run.shares().share_A.iloc[-1] != run.shares().share_A.iloc[-1]  # NaN, not division error
    assert validate_run(run).passed


def test_immigration_counts_and_effect():
    shock = immigration_shock("high_b_source", start_step=10, count_per_step=1000, duration_steps=2)
    run = simulate(replace(SMALL, scenario="imm", shocks=(shock,)))
    ts = run.timeseries
    assert ts.immigrants.sum() == 2000
    assert ts.loc[ts.step == 10, "immigrants"].item() == 1000
    s = run.shares()
    assert s.share_a_B.iloc[12] > s.share_a_B.iloc[9]


def test_disease_shock_only_kills_affected_phenotype_in_excess():
    shock = disease_shock(("O",), start_step=5, duration_steps=10, mode="additional_probability", additional_probability=0.3)
    run = simulate(replace(SMALL, scenario="dis", shocks=(shock,)))
    s = run.shares()
    assert run.timeseries.deaths_disease.sum() > 0
    assert s.share_O.iloc[15] < s.share_O.iloc[4] - 0.05
    assert run.invariants_ok


def test_bottleneck_is_phenotype_neutral_in_expectation():
    diffs = []
    for k in range(6):
        cfg = replace(SMALL, seed=100 + k, initial_population=4000, horizon_steps=12,
                      shocks=(bottleneck_shock(fraction=0.5, start_step=10),))
        s = simulate(cfg).shares()
        diffs.append(s.share_a_O.iloc[10] - s.share_a_O.iloc[9])
    assert abs(np.mean(diffs)) < 0.02


def test_zero_magnitude_shocks_identical_to_baseline():
    base = simulate(SMALL)
    zero = simulate(replace(SMALL, scenario="zero", shocks=(
        immigration_shock(count_per_step=0, start_step=10),
        disease_shock(("A",), start_step=10, relative_risk=1.0),
        bottleneck_shock(fraction=0.0, start_step=20),
    )))
    assert base.timeseries.equals(zero.timeseries)


def test_mutation_counts_and_zero_rate():
    run = simulate(replace(SMALL, mutation=MutationConfig(rate=0.05)))
    assert run.timeseries.mutations.sum() > 0 and run.invariants_ok
    assert simulate(SMALL).timeseries.mutations.sum() == 0


def test_rh_hdn_produces_fetal_losses_and_sensitisation():
    cfg = replace(SMALL, selection=preset("rh_hdn"))
    sim = Simulation(cfg)
    for _ in range(40):
        sim.step()
    ts = sim.rows
    assert sum(r["fetal_losses"] for r in ts) > 0
    assert sim.pop.sensitized.any()


def test_hdn_requires_rh_module():
    with pytest.raises(ConfigError):
        replace(SMALL, include_rh=False, selection=preset("rh_hdn")).validate()


def test_strong_selection_moves_frequency():
    run = simulate(replace(SMALL, horizon_steps=120, initial_population=3000, selection=preset("strong_o_advantage")))
    s = run.shares()
    assert s.share_a_O.iloc[-1] > s.share_a_O.iloc[0]


@pytest.mark.parametrize(
    "change",
    [
        dict(initial_population=1),
        dict(initial_population=10**7),
        dict(horizon_steps=0),
        dict(initialization_method="magic"),
        dict(shocks=(disease_shock((), start_step=3),)),
        dict(shocks=(bottleneck_shock(fraction=2.0, start_step=3),)),
        dict(shocks=(immigration_shock(start_step=999),)),
    ],
)
def test_invalid_configs_rejected(change):
    with pytest.raises(ConfigError):
        replace(SMALL, **change).validate()


def test_config_json_roundtrip():
    cfg = replace(SMALL, shocks=(immigration_shock(), disease_shock(("A", "AB"), affected_rh=("Rh-",))),
                  selection=preset("o_survival_advantage"))
    again = SimulationConfig.from_json(cfg.to_json())
    assert again == cfg
    with pytest.raises(ConfigError):
        SimulationConfig.from_json('{"bogus_field": 1}')
