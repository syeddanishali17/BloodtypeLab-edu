import time

import pandas as pd
import streamlit as st

from bloodtypelab.config import ConfigError
from bloodtypelab.experiments import (
    Scenario,
    batch_long_table,
    default_seeds,
    endpoint_table,
    paired_differences,
    run_scenario_batch,
    summarize_replicates,
)
from bloodtypelab.exports import zip_runs
from bloodtypelab.selection import PRESETS, preset
from ui.charts import band
from ui.controls import bottleneck_controls, config_summary, disease_controls, immigration_controls, init_defaults, model_settings
from ui.theme import SCENARIO_COLORS, badge

PREFIX = "cmp"
init_defaults(PREFIX, n=3000, years=120)
st.session_state.setdefault("cmp_scen", ["Immigration", "Disease"])
st.session_state.setdefault("cmp_reps", 10)
st.session_state.setdefault("cmp_fit", "o_survival_advantage")

st.title("Scenario comparison", icon=":material/compare_arrows:")
st.caption(
    "Task 3: every scenario runs with the **same list of seeds**. Seed *s* gives an identical starting population in every "
    "scenario, so differences are measured per seed (paired) and then summarised as mean and 2.5–97.5 % band."
)

settings_col, results_col = st.columns([1, 2.35], gap="large")
with settings_col:
    with st.container(border=True):
        st.markdown("**Shared settings** (identical in all scenarios)")
        base = model_settings(PREFIX)
        if base.selection.preset != "neutral":
            st.caption(":orange[The shared fitness preset is not neutral. The baseline will include it too.]")
    with st.container(border=True):
        st.markdown("**Scenarios**")
        st.caption("Baseline (no shocks) is always included.")
        st.pills("Compare baseline with", ["Immigration", "Disease", "Bottleneck", "Fitness rule"], selection_mode="multi",
                 key="cmp_scen", persist_state="session", label_visibility="collapsed")
        chosen = st.session_state.cmp_scen or []
        horizon = base.horizon_steps
        scenarios = [Scenario("baseline", "Baseline", description="No shocks")]
        if "Immigration" in chosen:
            with st.expander("Immigration settings", icon=":material/flight_land:"):
                imm = immigration_controls(PREFIX, horizon)
            scenarios.append(Scenario("immigration", "Immigration", (imm,), description=imm.describe()))
        if "Disease" in chosen:
            with st.expander("Disease settings", icon=":material/coronavirus:"):
                dis = disease_controls(PREFIX, horizon, base.include_rh)
            scenarios.append(Scenario("disease", "Disease", (dis,), description=dis.describe()))
        if "Bottleneck" in chosen:
            with st.expander("Bottleneck settings", icon=":material/compress:"):
                bn = bottleneck_controls(PREFIX, horizon)
            scenarios.append(Scenario("bottleneck", "Bottleneck", (bn,), description=bn.describe()))
        if "Fitness rule" in chosen:
            with st.expander("Fitness rule", icon=":material/science:"):
                opts = [k for k in PRESETS if k != "neutral"]
                st.selectbox("Preset", opts, format_func=lambda k: PRESETS[k]["title"], key="cmp_fit", persist_state="session")
                st.caption(PRESETS[st.session_state.cmp_fit]["description"])
            scenarios.append(Scenario("fitness", "Fitness rule", (), preset(st.session_state.cmp_fit),
                                      description=PRESETS[st.session_state.cmp_fit]["title"]))
    st.slider("Replicates per scenario", 2, 50, key="cmp_reps", persist_state="session",
              help="More replicates estimate the run-to-run distribution more reliably; they do not necessarily narrow its spread. Use 30+ for the report.")
    reps = int(st.session_state.cmp_reps)
    load = sum(s.apply(base, 0).estimated_agent_years() for s in scenarios) * reps
    st.caption(f"{len(scenarios)} scenarios × {reps} replicates = {len(scenarios) * reps} runs · ≈ {load / 1e6:.0f} M agent-years "
               f"(~{max(load / 2.5e7, 0.5):.0f} s)")
    run_clicked = st.button("Run comparison", type="primary", icon=":material/play_arrow:", width="stretch")

if run_clicked:
    with results_col:
        try:
            bar = st.progress(0.0, text="Starting…")
            t0 = time.perf_counter()

            def _p(done: int, total: int, label: str) -> None:
                bar.progress(done / total, text=f"{label}: run {done} of {total}")

            batch = run_scenario_batch(base, scenarios, default_seeds(reps, base.seed), progress=_p)
            bar.empty()
            st.session_state.batch = batch
            st.session_state.cmp_error = None
            st.session_state.flash = f"{len(batch.all_runs())} runs finished in {time.perf_counter() - t0:.1f} s"
            st.rerun()
        except (ConfigError, ValueError) as exc:
            st.session_state.cmp_error = str(exc)

with results_col:
    if st.session_state.get("cmp_error"):
        st.error(st.session_state.cmp_error, title="Comparison not run. Previous results kept", icon=":material/error:")
    batch = st.session_state.batch
    if batch is None:
        with st.container(border=True):
            st.markdown("### No comparison yet")
            st.markdown(
                "Pick the scenarios on the left and press **Run comparison**. A good first experiment: "
                "baseline vs **immigration** from a high-B source vs a **disease** that raises mortality of group A for five years."
            )
            st.caption("Tip: add **Bottleneck** as a control. It kills people at random, so the change you see is drift.")
        st.stop()

    colors = {s.label: SCENARIO_COLORS.get(s.name, "#6B6166") for s in batch.scenarios}
    head = st.container(horizontal=True, vertical_alignment="center")
    with head:
        st.markdown(f"#### {len(batch.scenarios)} scenarios × {len(batch.seeds)} paired seeds")
        badge("simulated")
        badge("hypothetical")
        if batch.invariants_ok:
            st.badge("Invariants hold in all runs", icon=":material/check_circle:", color="green")
        else:
            st.badge("Invariant failure", icon=":material/error:", color="red")
    st.caption(config_summary(batch.base_config) + f" · seeds {batch.seeds[0]}–{batch.seeds[-1]}")
    for s in batch.scenarios:
        st.caption(f"**{s.label}:** {s.description}")

    controls = st.container(horizontal=True, gap="medium", wrap=True)
    family = controls.segmented_control("Quantity", ["Phenotype shares", "Allele frequencies", "Rh-negative share", "Population size"],
                                  default="Phenotype shares", required=True, key="cmp_family", persist_state="session")
    mode = controls.segmented_control("Show", ["Trajectories", "Difference vs baseline"], default="Trajectories", required=True,
                                key="cmp_mode", persist_state="session")
    if family == "Phenotype shares":
        metrics, scale, unit = {f"share_{p}": f"Group {p}" for p in ("A", "B", "AB", "O")}, 100.0, "%"
    elif family == "Allele frequencies":
        metrics, scale, unit = {f"share_a_{a}": f"Allele {a}" for a in ("A", "B", "O")}, 100.0, "%"
    elif family == "Rh-negative share":
        metrics, scale, unit = {"share_rh_neg": "Rh-negative"}, 100.0, "%"
    else:
        metrics, scale, unit = {"population": "Population"}, 1.0, "agents"
    diff = mode == "Difference vs baseline"
    y_title = ("Δ vs baseline (" + ("pp" if unit == "%" else unit) + ")") if diff else f"Share ({unit})" if unit == "%" else "Agents"

    all_shocks = tuple(sh for s in batch.scenarios for sh in s.shocks)
    ncols = 2 if len(metrics) > 1 else 1
    grid = st.columns(ncols)
    for i, (col, label) in enumerate(metrics.items()):
        frames = []
        for s in batch.scenarios:
            if diff:
                if s.name == batch.baseline:
                    continue
                d = paired_differences(batch, s.name, col, scale)
            else:
                d = summarize_replicates(batch.runs[s.name], col)
                for k in ("mean", "p025", "p975"):
                    d[k] = d[k] * scale
            d["scenario"] = s.label
            frames.append(d)
        if not frames:
            grid[i % ncols].info("Add at least one non-baseline scenario to see differences.")
            continue
        data = pd.concat(frames)
        with grid[i % ncols]:
            st.altair_chart(band(data, colors, y_title, label, all_shocks, height=250, zero_rule=diff, legend=i == 0),
                            alt=f"{label}: {'difference to baseline' if diff else 'mean and 95 % band'} per scenario")
    st.caption(
        "Line = mean over replicates; band = empirical 2.5–97.5 percentiles. "
        + ("Differences are computed per seed (same starting population) before averaging. " if diff else "")
        + "These bands describe variation across runs, not a confidence interval for the mean. Band overlap or inclusion of zero is not a significance test."
    )

    st.subheader("Effect at a chosen year", icon=":material/table_chart:")
    year = st.slider("Year", 0, batch.base_config.horizon_steps, batch.base_config.horizon_steps,
                     key=f"cmp_year_{batch.base_config.horizon_steps}")
    cols = [c for c in metrics if c != "population"] or ["population"]
    et = endpoint_table(batch, cols, step=year, scale=scale)
    et["metric"] = et["metric"].map(metrics)
    fmt = "%.2f" if unit == "%" else "%.0f"
    st.dataframe(
        et.drop(columns=["step"]), hide_index=True, alt=f"Scenario summary at year {year}",
        column_config={
            "scenario": "Scenario", "metric": "Quantity",
            "mean": st.column_config.NumberColumn(f"Mean ({unit})", format=fmt),
            "p025": st.column_config.NumberColumn("2.5 %", format=fmt),
            "p975": st.column_config.NumberColumn("97.5 %", format=fmt),
            "diff_mean": st.column_config.NumberColumn("Δ vs baseline", format=fmt, help="Paired mean difference (pp for shares)."),
            "diff_p025": st.column_config.NumberColumn("Δ 2.5 %", format=fmt),
            "diff_p975": st.column_config.NumberColumn("Δ 97.5 %", format=fmt),
        },
    )

    with st.expander("Export this experiment", icon=":material/download:"):
        st.caption("Per-run folders (manifest, CSV, validation) plus one long table with every run, step and share.")
        with st.container(horizontal=True):
            st.download_button(
                "All runs (ZIP)", type="primary", icon=":material/folder_zip:", mime="application/zip",
                file_name="bloodtypelab_comparison.zip",
                data=lambda: zip_runs(batch.all_runs(), {"all_runs_long.csv": batch_long_table(batch).to_csv(index=False).encode()}),
            )
            st.download_button("Long table (CSV)", icon=":material/table_chart:", mime="text/csv",
                               file_name="bloodtypelab_comparison_long.csv",
                               data=lambda: batch_long_table(batch).to_csv(index=False).encode())
            st.download_button("Summary at selected year (CSV)", icon=":material/summarize:", mime="text/csv",
                               file_name=f"bloodtypelab_summary_year{year}.csv", data=et.to_csv(index=False).encode())

