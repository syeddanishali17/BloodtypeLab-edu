import pandas as pd
import streamlit as st

from bloodtypelab.anylogic_bridge import (
    OUTPUT_COLUMNS,
    bundle_zip,
    compare_with_anylogic,
    demo_anylogic_output,
    python_reference_runs,
    read_anylogic_output,
)
from bloodtypelab.config import ConfigError, SimulationConfig
from ui.charts import docking_chart
from ui.controls import config_summary

st.title("AnyLogic bridge", icon=":material/sync_alt:")
st.caption(
    "AnyLogic cannot run our Python agents natively. The useful integration is **docking**: an independent AnyLogic "
    "implementation starts from the same agents and rules, and we test statistically whether both models agree."
)

st.subheader("Integration options", icon=":material/hub:")
st.dataframe(
    pd.DataFrame([
        {"Level": "1 · File-based docking", "How": "Python exports agents + rules as CSV; AnyLogic ABM runs them and writes yearly counts; this page compares.",
         "Licence": "Check installed edition and model-time limits", "Status": "Java model + generated AnyLogic project"},
        {"Level": "2 · Pypeline", "How": "AnyLogic calls a local Python interpreter (e.g. our HWE inference) via the Pypeline library.",
         "Licence": "Free add-on library", "Status": "Optional demo"},
        {"Level": "3 · Alpyne", "How": "Python steps and controls an exported AnyLogic model.",
         "Licence": "Depends on edition. Check first", "Status": "Exploratory"},
        {"Level": "4 · AnyLogic Cloud API", "How": "Python client runs uploaded models remotely.",
         "Licence": "Cloud account + API key, network", "Status": "Not recommended (local-first)"},
    ]),
    hide_index=True, alt="AnyLogic integration options",
)

st.subheader("Step 1 · Export the docking bundle", icon=":material/upload_file:")
cfg = st.session_state.get("studio_config") or (st.session_state.last_run.config if st.session_state.last_run else None)
if cfg is None:
    cfg = SimulationConfig(initial_population=2000, horizon_steps=100)
    st.caption("No studio run yet. Using a default baseline (2 000 agents, 100 years). Run the *Simulation studio* first to export your own settings.")
st.markdown(f"Configuration: {config_summary(cfg)} · scenario **{cfg.scenario}**")
st.download_button(
    "Download AnyLogic bundle (ZIP)", data=lambda: bundle_zip(cfg), file_name=f"bloodtypelab_anylogic_{cfg.scenario}.zip",
    mime="application/zip", type="primary", icon=":material/folder_zip:",
)
with st.expander("What is in the bundle and how to build the AnyLogic model", icon=":material/description:"):
    st.markdown(
        "- `agents.csv`: every initial agent (id, sex, age, paternal and maternal ABO and RhD alleles)\n"
        "- `parameters.csv`, `mortality_table.csv` (q by age), `fertility_table.csv` (f by age), `selection.csv`, `shocks.csv`\n"
        "- `BloodTypeLab.alp`: an AnyLogic project that schedules the independent Java agent model\n"
        "- `BloodTypeModel.java`: the same Java core, runnable with Java 11+ without AnyLogic\n"
        "- `mutation_matrix.csv`: the ABO mutation probabilities\n"
        "- `anylogic_output_TEMPLATE.csv`: the file AnyLogic must write back\n\n"
        "Unzip, open **BloodTypeLab.alp**, set Main's **bundleDirectory** to that folder and run **Simulation**. "
        "A cyclic event advances the Java model once per year. Main's **replicateCount** controls repeated runs. "
        "Each run writes a separate CSV. Full instructions and the editor-validation limitation: `docs/anylogic_integration.md`."
    )
    st.code(",".join(["replicate"] + OUTPUT_COLUMNS) + "\n0,0,2000,830,301,139,730,1620\n0,1,2003,...", language="csv")

st.subheader("Step 2 · Docking test", icon=":material/compare:")
c1, c2 = st.columns([1.4, 1], gap="large")
with c1:
    up = st.file_uploader("AnyLogic output CSV files", type=["csv", "txt"], key="al_upload", accept_multiple_files=True,
                          help="Upload all replicate CSVs together. Include every year, replicate ID, bundle_id, and rh_pos when RhD is enabled.")
    st.caption("No AnyLogic model yet? Generate a demo file **from Python** in the same format to see how the test works.")
    demo = st.button("Use Python-generated demo file", icon=":material/science:",
                     help="Creates a file in the AnyLogic output format from the Python model itself, so you can see the test. It is not an AnyLogic run.")
with c2:
    n_py = st.slider("Python reference replicates", 10, 60, 30, 5, key="al_npy",
                     help="Same initial population as the bundle (same seed), different random dynamics.")

source = None
if demo:
    with st.spinner("Generating demo output…"):
        source = ("demo", demo_anylogic_output(cfg, n_replicates=5))
elif up:
    try:
        source = ("upload", read_anylogic_output(pd.concat([read_anylogic_output(f.getvalue()) for f in up], ignore_index=True)))
    except Exception as exc:
        st.error(str(exc), title="Could not read the AnyLogic file", icon=":material/error:")

if source is not None:
    try:
        with st.spinner(f"Running {n_py} Python reference replicates…"):
            py_runs = python_reference_runs(cfg, n_py)
            report = compare_with_anylogic(source[1], py_runs)
        st.session_state.docking = (source[0], report, cfg)
    except (ConfigError, ValueError) as exc:
        st.error(str(exc), title="Docking failed", icon=":material/error:")

if st.session_state.docking:
    kind, report, dcfg = st.session_state.docking
    if kind == "demo":
        st.warning("This comparison uses a demo file generated by the Python model itself. It demonstrates the test, "
                   "it is **not** evidence about an AnyLogic model.", icon=":material/info:")
    message = st.success if report.consistent else (st.warning if not report.sufficient_evidence and report.rows.passed.all() else st.error)
    message(report.verdict)
    st.caption(f"{report.n_anylogic_replicates} AnyLogic replicate(s) vs {report.n_python_replicates} Python replicates. " + " ".join(report.notes))
    st.dataframe(
        report.rows, hide_index=True, alt="Docking statistics per phenotype",
        column_config={
            "metric": "Quantity",
            "steps_compared": st.column_config.NumberColumn("Years", format="%d"),
            "inside_95_band": st.column_config.ProgressColumn("Inside Python 95 % band", min_value=0.0, max_value=1.0, format="percent"),
            "final_python_mean": st.column_config.NumberColumn("Final Python mean", format="%.2f"),
            "final_anylogic_mean": st.column_config.NumberColumn("Final external mean", format="%.2f"),
            "max_abs_t": st.column_config.NumberColumn("max |t|", format="%.2f"),
            "min_adjusted_p": st.column_config.NumberColumn("Smallest adjusted p", format="%.4f"),
            "ks_p_value": st.column_config.NumberColumn("KS p", format="%.3f"),
            "passed": st.column_config.CheckboxColumn("Pass"),
        },
    )
    cols = st.columns(2)
    for i, (metric, b) in enumerate(report.bands.items()):
        bdf = b.copy()
        scale = 1 if metric == "population" else 100
        for k in ("mean", "p025", "p975"):
            bdf[k] = bdf[k] * scale
        al = report.anylogic_shares[["replicate", "step", metric]].rename(columns={metric: "value"})
        al["value"] = al["value"] * scale
        label = "Population (people)" if metric == "population" else metric.replace("share_", "").replace("rh_pos", "Rh+") + " (%)"
        with cols[i % 2]:
            st.altair_chart(docking_chart(bdf, al, label), alt=f"Python band versus AnyLogic replicates for {label}")
    st.caption("Grey: Python mean and 2.5–97.5 % band. Red: each AnyLogic replicate.")
