"""BloodTypeLab - Streamlit entry point.

Run:  python -m streamlit run app.py --server.address 127.0.0.1
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from bloodtypelab import __version__  # noqa: E402
from ui.state import init_state  # noqa: E402

st.set_page_config(
    page_title="BloodTypeLab",
    page_icon=":material/bloodtype:",
    layout="wide",
    initial_sidebar_state="expanded",
)
init_state()

P = "app_pages"
# A flat list. Section headers collapse on click and hide pages, with no obvious control to open them again.
pages = [
    st.Page(f"{P}/overview.py", title="Overview", icon=":material/home:", default=True,
            help="The assignment, how the model works, and a guided demo path."),
    st.Page(f"{P}/genetics_lab.py", title="Genetics lab", icon=":material/genetics:",
            help="Punnett squares and simulated crosses compared with Mendelian theory."),
    st.Page(f"{P}/population.py", title="Population explorer", icon=":material/groups:",
            help="Build synthetic people from the Austrian blood-group shares, then inspect genotypes and ages."),
    st.Page(f"{P}/simulation.py", title="Simulation studio", icon=":material/play_circle:",
            help="One run: baseline, a shock, or a fitness rule. The plot updates when the run finishes."),
    st.Page(f"{P}/comparison.py", title="Scenario comparison", icon=":material/compare_arrows:",
            help="Same seeds for the baseline and the shocks, so the difference is not a lucky start."),
    st.Page(f"{P}/validation.py", title="Validation & evidence", icon=":material/verified:",
            help="Run the checks in this session. A tick appears only after that check has run."),
    st.Page(f"{P}/anylogic.py", title="AnyLogic bridge", icon=":material/sync_alt:",
            help="Download a bundle for AnyLogic and compare an uploaded CSV with this model."),
    st.Page(f"{P}/methods.py", title="Methods & references", icon=":material/menu_book:",
            help="Yearly order, parameters, assumptions, and the bibliography."),
]
page = st.navigation(pages, position="sidebar", expanded=True)

flash = st.session_state.pop("flash", None)
if flash:
    st.toast(flash, icon=":material/check_circle:")

with st.sidebar:
    run = st.session_state.get("last_run")
    with st.container(border=True):
        st.caption("Last completed run")
        if run is None:
            st.markdown("No run yet. Open **Simulation studio**.")
        else:
            st.markdown(f"**{run.scenario}**")
            st.caption(f"Seed {run.seed}")
            st.caption(f"{run.config.initial_population:,} agents · {run.config.horizon_steps} years")
            if run.invariants_ok:
                st.badge("Invariants hold", icon=":material/check_circle:", color="green",
                         help="Each year the books balanced: population, births, deaths, allele counts and ids.")
            else:
                st.badge("Invariant failure", icon=":material/error:", color="red",
                         help="A yearly check failed. The run stopped or is marked bad. See Validation for the detail.")
    st.caption(f"v{__version__} · educational model, not a forecast. Theme: menu at the top right.")

page.run()
