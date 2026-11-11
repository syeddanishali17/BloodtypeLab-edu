import io
import json
import zipfile
from dataclasses import replace

import pytest

from bloodtypelab.anylogic_bridge import (
    bundle_files,
    compare_with_anylogic,
    demo_anylogic_output,
    python_reference_runs,
    read_anylogic_output,
)
from bloodtypelab.config import ConfigError, SimulationConfig
from bloodtypelab.engine import simulate
from bloodtypelab.experiments import (
    Scenario,
    endpoint_table,
    paired_differences,
    run_scenario_batch,
    summarize_replicates,
)
from bloodtypelab.exports import export_run, run_file_bytes, zip_runs
from bloodtypelab.shocks import disease_shock, immigration_shock
from bloodtypelab.validation import run_verification_suite

BASE = SimulationConfig(initial_population=1200, horizon_steps=40, seed=1)
SCEN = [
    Scenario("baseline", "Baseline"),
    Scenario("immigration", "Immigration", (immigration_shock("high_b_source", start_step=10, count_per_step=600),)),
    Scenario("disease", "Disease", (disease_shock(("A",), start_step=10, duration_steps=5, relative_risk=4.0),)),
]


@pytest.fixture(scope="module")
def batch():
    return run_scenario_batch(BASE, SCEN, [1, 2, 3, 4])


def test_batch_shapes_and_pairing(batch):
    assert set(batch.runs) == {"baseline", "immigration", "disease"}
    assert all(len(v) == 4 for v in batch.runs.values())
    for i in range(4):  # identical start per seed
        assert batch.runs["baseline"][i].agents_start.equals(batch.runs["disease"][i].agents_start)
    assert batch.invariants_ok


def test_summary_and_differences(batch):
    s = summarize_replicates(batch.runs["baseline"], "share_O")
    assert len(s) == 41 and (s.p025 <= s["mean"]).all() and (s["mean"] <= s.p975).all()
    d = paired_differences(batch, "baseline", "share_O")
    assert (d["mean"].abs() < 1e-12).all()  # baseline minus itself
    d2 = paired_differences(batch, "immigration", "share_a_B", 100)
    assert d2["mean"].iloc[-1] > 0  # high-B immigrants raise B allele share (percentage points)
    d3 = paired_differences(batch, "disease", "share_A", 100)
    assert (d3["mean"].iloc[:10].abs() < 1e-12).all()  # identical before the shock
    assert d3["mean"].iloc[16] < 0
    ep = endpoint_table(batch, ["share_A", "share_O"])
    assert set(ep.scenario) == {"Baseline", "Immigration", "Disease"}


def test_batch_rejects_bad_input():
    with pytest.raises(ConfigError):
        run_scenario_batch(BASE, SCEN, [1, 1])
    with pytest.raises(ConfigError):
        run_scenario_batch(BASE, [], [1])


def test_export_contract_and_immutability(tmp_path):
    run = simulate(BASE)
    folder = export_run(run, tmp_path)
    names = {p.name for p in folder.iterdir()}
    for required in ("manifest.json", "population_timeseries.csv", "phenotype_timeseries.csv",
                     "genotype_timeseries.csv", "allele_timeseries.csv", "validation_summary.json", "rh_timeseries.csv"):
        assert required in names
    man = json.loads((folder / "manifest.json").read_text())
    assert man["seed"] == 1 and man["status"] == "completed" and man["invariants_ok"]
    assert "phenotype_timeseries.csv" in man["files"] and len(man["files"]["phenotype_timeseries.csv"]) == 64
    assert man["reference"]["reference_id"] == "austria_gesundheitsportal_2022"
    with pytest.raises(FileExistsError):
        export_run(run, tmp_path)
    assert not any(p.name.endswith(".partial") for p in tmp_path.iterdir())


def test_zip_contains_all_runs():
    runs = [simulate(BASE), simulate(replace(BASE, seed=2))]
    zf = zipfile.ZipFile(io.BytesIO(zip_runs(runs)))
    assert sum(n.endswith("manifest.json") for n in zf.namelist()) == 2
    files = run_file_bytes(runs[0])
    assert b"share" in files["phenotype_timeseries.csv"].splitlines()[0]


def test_anylogic_bundle_and_docking():
    files = bundle_files(BASE)
    for name in ("agents.csv", "parameters.csv", "mortality_table.csv", "fertility_table.csv", "shocks.csv"):
        assert name in files
    assert files["agents.csv"].count(b"\n") == BASE.initial_population + 1
    py_runs = python_reference_runs(BASE, 20)
    assert all(r.agents_start.equals(py_runs[0].agents_start) for r in py_runs)
    al = demo_anylogic_output(BASE, n_replicates=5)
    rep = compare_with_anylogic(al, py_runs)
    assert rep.consistent, rep.rows
    # a clearly different model must be flagged
    bad = al.copy()
    bad["n_O"] = bad["n_O"] + bad["n_A"]
    bad["n_A"] = 0
    rep_bad = compare_with_anylogic(bad, py_runs)
    assert not rep_bad.consistent


def test_anylogic_output_validation():
    with pytest.raises(ValueError):
        read_anylogic_output(b"step,population\n0,10\n")
    with pytest.raises(ValueError):
        read_anylogic_output(b"step,population,n_A,n_B,n_AB,n_O\n0,10,1,1,1,1\n")


def test_live_verification_suite_passes():
    checks = run_verification_suite(n_births=10_000, quick=True)
    failed = [c for c in checks if not c.passed]
    assert not failed, failed
