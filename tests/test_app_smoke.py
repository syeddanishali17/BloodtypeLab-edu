"""Headless Streamlit smoke tests: every page renders without exceptions; main actions work."""
from pathlib import Path

import pytest

st_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = st_testing.AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")
PAGES = [
    "app_pages/overview.py",
    "app_pages/genetics_lab.py",
    "app_pages/population.py",
    "app_pages/simulation.py",
    "app_pages/comparison.py",
    "app_pages/validation.py",
    "app_pages/anylogic.py",
    "app_pages/methods.py",
]


def _new():
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    assert not at.exception, at.exception
    return at


@pytest.mark.parametrize("page", PAGES)
def test_page_renders(page):
    at = _new()
    at.switch_page(page)
    at.run()
    assert not at.exception, [e.value for e in at.exception]


def _click(at, label):
    for b in at.button:
        if b.label == label:
            b.click()
            at.run()
            return
    raise AssertionError(f"button {label!r} not found; have {[b.label for b in at.button]}")


def test_simulation_run_and_shock():
    at = _new()
    at.switch_page("app_pages/simulation.py")
    at.session_state["sim_n"] = 800
    at.session_state["sim_years"] = 40
    at.run()
    _click(at, "Run simulation")
    assert not at.exception, [e.value for e in at.exception]
    run = at.session_state["last_run"]
    assert run is not None and run.invariants_ok and run.config.initial_population == 800
    # switch on a disease shock and run again; the previous run is replaced only on success
    at.session_state["sim_use_dis"] = True
    at.run()
    _click(at, "Run simulation")
    assert at.session_state["last_run"].scenario == "disease"
    for view in ("Alleles", "Genotypes", "Rh factor", "Population & events", "Agents"):
        at.session_state["sim_view"] = view
        at.run()
        assert not at.exception, (view, [e.value for e in at.exception])


def test_comparison_run():
    at = _new()
    at.switch_page("app_pages/comparison.py")
    at.session_state["cmp_n"] = 500
    at.session_state["cmp_years"] = 30
    at.session_state["cmp_reps"] = 3
    at.session_state["cmp_scen"] = ["Immigration", "Bottleneck"]
    at.run()
    _click(at, "Run comparison")
    assert not at.exception, [e.value for e in at.exception]
    batch = at.session_state["batch"]
    assert set(batch.runs) == {"baseline", "immigration", "bottleneck"}
    at.session_state["cmp_mode"] = "Difference vs baseline"
    at.run()
    assert not at.exception


def test_genetics_lab_homozygous_parents():
    at = _new()
    at.switch_page("app_pages/genetics_lab.py")
    for father, mother in (("AA", "AA"), ("BB", "BB"), ("OO", "OO"), ("AA", "BO"), ("AO", "BO")):
        at.session_state["gl_p1"] = father
        at.session_state["gl_p2"] = mother
        at.run()
        assert not at.exception, (father, mother, [e.value for e in at.exception])


def test_population_and_genetics_actions():
    at = _new()
    at.switch_page("app_pages/population.py")
    at.session_state["pe_n"] = 1000
    at.run()
    _click(at, "Generate population")
    assert not at.exception and at.session_state["population_preview"] is not None


def test_anylogic_demo_docking():
    at = _new()
    at.switch_page("app_pages/anylogic.py")
    at.run()
    at.slider(key="al_npy").set_value(10)
    at.run()
    _click(at, "Use Python-generated demo file")
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["docking"] is not None
