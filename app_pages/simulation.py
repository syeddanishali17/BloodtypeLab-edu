import pandas as pd
import streamlit as st

from bloodtypelab.config import ConfigError, SimulationConfig
from bloodtypelab.engine import InvariantError, simulate
from bloodtypelab.exports import run_tables, zip_runs
from bloodtypelab.genetics import ABO_GENOTYPES, ABO_PHENOTYPES
from bloodtypelab.validation import validate_run
from ui.charts import lines, population_and_events, stacked_area, to_long
from ui.controls import (
    apply_config_to_state,
    bottleneck_controls,
    config_summary,
    disease_controls,
    immigration_controls,
    init_defaults,
    model_settings,
    with_shocks,
)
from ui.state import push_run
from ui.theme import ALLELE_COLORS, GENO_COLORS, PHENO_COLORS, RH_COLORS, badge

PREFIX = "sim"
init_defaults(PREFIX)

st.title("Simulation studio", icon=":material/play_circle:")
st.caption("Configure one run, press **Run simulation**, explore the result. Changing settings never alters a finished run.")


def _load_config() -> None:
    f = st.session_state.get("sim_upload")
    if f is None:
        return
    try:
        cfg = SimulationConfig.from_json(f.getvalue().decode("utf-8")).validate()
        apply_config_to_state(PREFIX, cfg)
        st.session_state.sim_load_msg = ("ok", f"Loaded configuration '{f.name}'.")
    except Exception as exc:  # show any parsing/validation problem to the user
        st.session_state.sim_load_msg = ("error", f"Could not load '{f.name}': {exc}")


settings_col, results_col = st.columns([1, 2.35], gap="large")

# ------------------------------------------------------------------ settings (draft)
with settings_col:
    with st.container(border=True):
        st.markdown("**Model settings**")
        base = model_settings(PREFIX)
    with st.container(border=True):
        st.markdown("**External shocks** (Task 3)")
        horizon = base.horizon_steps
        shocks = []
        if st.toggle("Immigration", key="sim_use_imm", persist_state="session"):
            with st.container(border=True):
                shocks.append(immigration_controls(PREFIX, horizon))
        if st.toggle("Blood-type-specific disease", key="sim_use_dis", persist_state="session"):
            with st.container(border=True):
                shocks.append(disease_controls(PREFIX, horizon, base.include_rh))
        if st.toggle("Bottleneck (neutral control)", key="sim_use_bn", persist_state="session"):
            with st.container(border=True):
                shocks.append(bottleneck_controls(PREFIX, horizon))
        if not shocks:
            st.caption("No shocks: this is the **baseline** scenario.")
    scenario = "+".join(s.kind for s in shocks) or "baseline"
    draft = with_shocks(base, shocks, scenario)

    run_clicked = st.button("Run simulation", type="primary", icon=":material/play_arrow:", width="stretch")
    est = draft.estimated_agent_years()
    st.caption(f"≈ {est / 1e6:.1f} M agent-years · typically {max(est / 2.5e7, 0.1):.1f} s on a laptop")

    with st.expander("Save or load configuration", icon=":material/save:"):
        st.download_button("Save current settings (JSON)", data=draft.to_json(), file_name=f"bloodtypelab_{scenario}.json",
                           mime="application/json", icon=":material/download:", width="stretch")
        st.file_uploader("Load settings (JSON)", type=["json"], key="sim_upload", on_change=_load_config)
        msg = st.session_state.pop("sim_load_msg", None)
        if msg:
            (st.success if msg[0] == "ok" else st.error)(msg[1])

# ------------------------------------------------------------------ run
if run_clicked:
    with results_col:
        try:
            cfg = draft.validate()
            bar = st.progress(0.0, text="Simulating…")

            def _progress(t: int, total: int) -> None:
                if t % 5 == 0 or t == total:
                    bar.progress(t / total, text=f"Simulating year {t} of {total}")

            run = simulate(cfg, progress=_progress)
            bar.empty()
            push_run(run)
            st.session_state.studio_config = cfg
            st.session_state.last_error = None
            st.session_state.flash = f"Run finished in {run.elapsed_seconds:.2f} s"
            st.rerun()
        except (ConfigError, InvariantError, ValueError) as exc:
            st.session_state.last_error = str(exc)

# ------------------------------------------------------------------ results (completed run only)
with results_col:
    if st.session_state.last_error:
        st.error(st.session_state.last_error, title="The run was not started or failed. The previous result is kept",
                 icon=":material/error:")
    run = st.session_state.last_run
    if run is None:
        with st.container(border=True):
            st.markdown("### No completed run yet")
            st.markdown(
                "Start with the defaults: a **neutral baseline** of 5 000 agents over 150 years, initialised from the "
                "Austrian distribution. Then switch on a shock or a fitness rule and run again."
            )
            st.caption("Results appear here and in the sidebar. Every run gets a unique ID, seed and manifest.")
        st.stop()

    cfg = run.config
    if cfg != draft:
        st.caption(":orange[Settings on the left differ from the run shown below. Press **Run simulation** to apply them.]")

    head = st.container(horizontal=True, vertical_alignment="center", gap="small")
    with head:
        st.markdown(f"#### {run.scenario}")
        badge("observed" if run.reference["kind"] == "observed" else "synthetic")
        badge("simulated")
        if cfg.shocks or cfg.selection.status != "control":
            badge("hypothetical")
        if run.invariants_ok:
            st.badge("Invariants hold every year", icon=":material/check_circle:", color="green")
        else:
            st.badge(f"{len(run.invariant_failures)} invariant failures", icon=":material/error:", color="red")
    st.caption(f"Run `{run.run_id}` · {config_summary(cfg)} · {run.elapsed_seconds:.2f} s")
    for w in run.warnings:
        st.caption(f":material/info: {w}")

    sh = run.shares()
    ts = run.timeseries
    first, last = sh.iloc[0], sh.iloc[-1]
    kpi = st.columns(5)
    kpi[0].metric("Population", f"{int(last.population):,}", delta=f"{int(last.population - first.population):+,}",
                  delta_color="off", border=True, chart_data=ts["population"].tolist(), chart_type="area")
    for col, p in zip(kpi[1:], ABO_PHENOTYPES):
        col.metric(f"Group {p}", f"{last[f'share_{p}'] * 100:.1f}%",
                   delta=f"{(last[f'share_{p}'] - first[f'share_{p}']) * 100:+.2f} pp", delta_color="off", border=True,
                   chart_data=(sh[f"share_{p}"] * 100).round(3).tolist(), chart_type="line",
                   help="Final share; delta is the change since year 0 in percentage points.")

    views = ["Phenotypes", "Alleles", "Genotypes", "Rh factor", "Population & events", "Agents"]
    if not cfg.include_rh:
        views.remove("Rh factor")
    view = st.segmented_control("View", views, default="Phenotypes", required=True, key="sim_view",
                                persist_state="session", label_visibility="collapsed")
    shocks_drawn = cfg.shocks

    if view == "Phenotypes":
        style = st.segmented_control("Chart style", ["Stacked", "Lines"], default="Stacked", required=True,
                                     key="sim_style", persist_state="session", label_visibility="collapsed")
        long = to_long(sh, {f"share_{p}": p for p in ABO_PHENOTYPES})
        if style == "Stacked":
            st.altair_chart(stacked_area(long, PHENO_COLORS, "Share of population (%)", shocks_drawn, "Phenotype", height=380),
                            alt="Stacked shares of blood groups A, B, AB and O over time")
        else:
            st.altair_chart(lines(long, PHENO_COLORS, "Share of population (%)", shocks_drawn, "Phenotype", height=380),
                            alt="Blood group shares over time as lines")
        st.caption("Shaded bands and dashed lines mark shocks. Hover for exact values.")
    elif view == "Alleles":
        long = to_long(sh, {f"share_a_{a}": a for a in ("A", "B", "O")})
        st.altair_chart(lines(long, ALLELE_COLORS, "Allele frequency (%)", shocks_drawn, "Allele", height=380, fmt=".2f"),
                        alt="ABO allele frequencies over time")
        h = to_long(sh, {"het_obs": "Observed", "het_exp": "Hardy-Weinberg expected"})
        st.altair_chart(lines(h, {"Observed": "#B4234A", "Hardy-Weinberg expected": "#6B6166"}, "Heterozygosity (%)", shocks_drawn,
                              "", height=220, fmt=".2f"),
                        alt="Observed versus Hardy-Weinberg expected heterozygosity")
        st.caption("Allele frequencies move only by drift, migration, selection or mutation. "
                   "Observed ≈ expected heterozygosity means the population stays close to Hardy-Weinberg equilibrium.")
    elif view == "Genotypes":
        long = to_long(sh, {f"share_g_{g}": g for g in ABO_GENOTYPES})
        st.altair_chart(stacked_area(long, GENO_COLORS, "Share of population (%)", shocks_drawn, "Genotype", height=380),
                        alt="Stacked ABO genotype shares over time")
    elif view == "Rh factor":
        long = to_long(sh, {"share_rh_pos": "Rh+", "share_rh_neg": "Rh-"})
        st.altair_chart(lines(long, RH_COLORS, "Share of population (%)", shocks_drawn, "Rh", height=300),
                        alt="Rh positive and negative shares over time")
        al = to_long(sh, {"share_a_D": "D", "share_a_d": "d"})
        st.altair_chart(lines(al, {"D": "#D55E00", "d": "#56B4E9"}, "Allele frequency (%)", shocks_drawn, "RhD allele", height=220),
                        alt="RhD allele frequencies over time")
        if ts["fetal_losses"].sum():
            st.caption(f"Rh-HDN active: {int(ts['fetal_losses'].sum()):,} pregnancies lost in total.")
    elif view == "Population & events":
        pop_c, ev_c = population_and_events(ts, shocks_drawn)
        st.altair_chart(pop_c, alt="Population size over time")
        st.altair_chart(ev_c, alt="Births, deaths by cause and immigrants per year")
        totals = ts[["births", "deaths", "deaths_disease", "deaths_bottleneck", "immigrants", "fetal_losses", "mutations"]].sum()
        st.dataframe(totals.rename("total over run").to_frame().T, hide_index=True, alt="Event totals")
        st.caption("Event axis is symmetric-log so rare events stay visible. Disease deaths are *excess* deaths beyond baseline risk.")
    else:
        a, b = st.columns(2)
        a.markdown("**Sample at year 0**")
        a.dataframe(run.agents_start, hide_index=True, height=380, alt="Agent sample at the start")
        b.markdown(f"**Sample at year {cfg.horizon_steps}**")
        b.dataframe(run.agents_end, hide_index=True, height=380, alt="Agent sample at the end")
        st.caption(f"First {cfg.agent_snapshot_size} living agents. Newborns have both parents' alleles: column *from father* / *from mother*.")

    with st.expander("Run checks and exports", icon=":material/download:"):
        rep = validate_run(run)
        st.dataframe(pd.DataFrame([c.as_dict() for c in rep.checks])[["name", "passed", "expected", "observed"]],
                     hide_index=True, alt="Run-level validation checks",
                     column_config={"passed": st.column_config.CheckboxColumn("Passed")})
        with st.container(horizontal=True):
            st.download_button("All result files (ZIP)", data=lambda: zip_runs([run]), file_name=f"{run.run_id}.zip",
                               mime="application/zip", icon=":material/folder_zip:", type="primary")
            st.download_button("Phenotype time series (CSV)",
                               data=lambda: run_tables(run)["phenotype_timeseries.csv"].to_csv(index=False).encode(),
                               file_name=f"{run.run_id}_phenotypes.csv", mime="text/csv", icon=":material/table_chart:")
            st.download_button("Run configuration (JSON)", data=cfg.to_json(), file_name=f"{run.run_id}_config.json",
                               mime="application/json", icon=":material/data_object:")
        st.caption("The ZIP holds manifest.json (config, seed, reference, SHA-256 hashes), CSV tables and validation_summary.json.")

    if len(st.session_state.run_history) > 1:
        with st.expander("Recent runs in this session", icon=":material/history:"):
            st.dataframe(
                pd.DataFrame([
                    {"run_id": r.run_id, "scenario": r.scenario, "seed": r.seed, "N0": r.config.initial_population,
                     "years": r.config.horizon_steps, "final A %": r.shares().share_A.iloc[-1] * 100,
                     "final O %": r.shares().share_O.iloc[-1] * 100, "invariants": r.invariants_ok}
                    for r in st.session_state.run_history
                ]),
                hide_index=True, alt="Recent runs",
                column_config={"final A %": st.column_config.NumberColumn(format="%.2f"),
                               "final O %": st.column_config.NumberColumn(format="%.2f")},
            )

