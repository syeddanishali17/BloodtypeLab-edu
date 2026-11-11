import pandas as pd
import streamlit as st

from bloodtypelab.config import ConfigError, SimulationConfig
from bloodtypelab.engine import rng_streams
from bloodtypelab.genetics import ABO_GENOTYPES, ABO_PHENOTYPES
from bloodtypelab.initialization import initialize_population
from bloodtypelab.reference import available_references, load_reference
from ui.charts import age_pyramid, grouped_bars
from ui.controls import INIT_METHODS
from ui.theme import badge

st.title("Population explorer", icon=":material/groups:")
st.caption("From four published percentages to thousands of individual synthetic people.")

refs = available_references()
defaults = {"pe_ref": "austria_gesundheitsportal_2022", "pe_n": 5000, "pe_seed": 20261111, "pe_init": "hwe_em",
            "pe_alloc": "multinomial", "pe_aa": 0.3, "pe_bb": 0.1}
for k, v in defaults.items():
    st.session_state.setdefault(k, v)

with st.container(border=True):
    c = st.columns([1.6, 1, 1, 1.6, 1.1], vertical_alignment="bottom")
    c[0].selectbox("Reference", list(refs), format_func=lambda r: refs[r]["title"], key="pe_ref", persist_state="session",
                   help="Published blood-group shares used as the target. The Austrian set is a real source. The synthetic demo is made up.")
    c[1].number_input("Agents", 100, 200_000, step=1000, key="pe_n", persist_state="session",
                      help="How many synthetic people to create. Smaller populations wander further from the target shares.")
    c[2].number_input("Seed", 0, 2**31 - 1, key="pe_seed", persist_state="session",
                      help="Same seed and same settings rebuild the same people.")
    c[3].selectbox("Genotype inference", list(INIT_METHODS), format_func=INIT_METHODS.get, key="pe_init", persist_state="session",
                   help="Blood group is what we observe. Genotype is what is inherited. Hardy-Weinberg fills in the hidden AA versus AO split. Explicit split lets you set that split yourself.")
    c[4].segmented_control("Allocation", ["multinomial", "quota"], required=True, key="pe_alloc", persist_state="session",
                           format_func={"multinomial": "Sampling", "quota": "Quota"}.get,
                           help="Sampling draws people at random, so the realised shares wobble. Quota hits the target counts exactly.")
    if st.session_state.pe_init == "explicit_split":
        s1, s2 = st.columns(2)
        s1.slider("Share of A that is AA", 0.0, 1.0, step=0.05, key="pe_aa", persist_state="session")
        s2.slider("Share of B that is BB", 0.0, 1.0, step=0.05, key="pe_bb", persist_state="session")
    generate = st.button("Generate population", type="primary", icon=":material/person_add:",
                         help="Builds a new starting population. The one on screen stays until this succeeds.")

if generate:
    try:
        cfg = SimulationConfig(
            initial_population=int(st.session_state.pe_n), seed=int(st.session_state.pe_seed),
            reference_id=st.session_state.pe_ref, initialization_method=st.session_state.pe_init,
            allocation=st.session_state.pe_alloc,
            explicit_split_aa_fraction=float(st.session_state.pe_aa), explicit_split_bb_fraction=float(st.session_state.pe_bb),
            horizon_steps=1,
        ).validate()
        ref = load_reference(cfg.reference_id)
        res = initialize_population(cfg, ref, rng_streams(cfg.seed)[0])
        st.session_state.population_preview = (cfg, ref, res)  # replaced only after success
        st.toast("Population generated", icon=":material/check_circle:")
    except (ConfigError, ValueError) as exc:
        st.error(str(exc), title="Could not generate the population", icon=":material/error:")

preview = st.session_state.population_preview
if preview is None:
    st.info("Choose settings and press **Generate population**. Nothing is generated automatically, so the previous population stays until a new one succeeds.",
            icon=":material/info:")
    st.stop()

cfg, ref, res = preview
inf = res.inference
st.markdown(
    f"Showing **{cfg.initial_population:,} agents**, seed `{cfg.seed}`, reference *{ref.title}*, inference *{INIT_METHODS[inf.method]}*."
)

st.subheader("1 · Reference → inferred genotypes", icon=":material/functions:")
with st.container(horizontal=True):
    badge("observed" if ref.kind == "observed" else "synthetic")
    st.markdown("→")
    badge("inferred")
    st.markdown("→")
    badge("simulated")
m = st.columns(4)
m[0].metric("Allele A frequency", f"{inf.allele_freqs['A']:.3f}", border=True,
            help="Share of all ABO alleles that are A. About twice a person's contribution, because everyone carries two.")
m[1].metric("Allele B frequency", f"{inf.allele_freqs['B']:.3f}", border=True,
            help="Share of all ABO alleles that are B.")
m[2].metric("Allele O frequency", f"{inf.allele_freqs['O']:.3f}", border=True,
            help="Share of all ABO alleles that are O. O is common even though many carriers look like group A or B.")
m[3].metric("Max. residual (inferred − reference)", f"{inf.max_abs_residual * 100:.2f} pp", border=True,
            help="Hardy-Weinberg cannot reproduce rounded percentages exactly; we report the gap instead of forcing a fit.")
for note in inf.notes:
    st.caption(note)

comp = pd.DataFrame(res.comparison_rows())
long = comp.melt(id_vars="category", var_name="source", value_name="share")
long["share"] *= 100
names = {"target_reference": "Reference", "inferred_hwe": "Inferred (model target)", "realised_initial": "Realised in agents"}
long["source"] = long["source"].map(names)
c1, c2 = st.columns([1.5, 1], gap="large")
with c1:
    st.altair_chart(
        grouped_bars(long, "category", "share", "source",
                     {"Reference": "#6B6166", "Inferred (model target)": "#7E22CE", "Realised in agents": "#B4234A"},
                     "Share (%)", x_sort=list(ABO_PHENOTYPES) + ["Rh+", "Rh-"], fmt=".2f"),
        alt="Reference, inferred and realised phenotype shares side by side",
    )
with c2:
    table = comp.copy()
    table["gap_pp"] = (table["realised_initial"] - table["target_reference"]) * 100
    st.dataframe(
        table, hide_index=True,
        column_config={
            "category": "Group",
            "target_reference": st.column_config.NumberColumn("Reference", format="percent"),
            "inferred_hwe": st.column_config.NumberColumn("Inferred", format="percent"),
            "realised_initial": st.column_config.NumberColumn("Realised", format="percent"),
            "gap_pp": st.column_config.NumberColumn("Realised − ref. (pp)", format="%.2f"),
        },
        alt="Table of reference, inferred and realised shares",
    )
    st.caption("Realised shares differ from the targets because of random sampling. Smaller populations differ more. Choose *Quota* allocation to remove this noise.")

st.subheader("2 · Hidden genotypes", icon=":material/visibility_off:")
g1, g2 = st.columns([1.5, 1], gap="large")
with g1:
    gdf = pd.DataFrame({
        "genotype": list(ABO_GENOTYPES),
        "Inferred": [inf.genotype_freqs[g] * 100 for g in ABO_GENOTYPES],
        "Realised": [res.realised["genotype"][g] * 100 for g in ABO_GENOTYPES],
    }).melt("genotype", var_name="source", value_name="share")
    st.altair_chart(
        grouped_bars(gdf, "genotype", "share", "source", {"Inferred": "#7E22CE", "Realised": "#B4234A"}, "Share (%)",
                     x_sort=list(ABO_GENOTYPES), fmt=".2f"),
        alt="Inferred and realised ABO genotype shares",
    )
with g2:
    ao = inf.genotype_freqs["AO"] / (inf.genotype_freqs["AA"] + inf.genotype_freqs["AO"])
    bo = inf.genotype_freqs["BO"] / (inf.genotype_freqs["BB"] + inf.genotype_freqs["BO"])
    st.metric("Group-A people who carry O", f"{ao:.0%}", border=True)
    st.metric("Group-B people who carry O", f"{bo:.0%}", border=True)
    st.caption("These carriers are invisible in phenotype statistics but pass O to half of their children.")

st.subheader("3 · Age, sex and individual agents", icon=":material/badge:")
a1, a2 = st.columns([1, 1.3], gap="large")
agents = res.population.to_frame(include_rh=cfg.include_rh)
with a1:
    st.altair_chart(age_pyramid(agents), alt="Age pyramid of the synthetic starting population")
    st.caption("Ages follow the stationary distribution of the illustrative mortality schedule (no Austrian census data yet).")
    badge("synthetic")
with a2:
    st.dataframe(
        agents.head(300), hide_index=True, height=360,
        column_config={"agent_id": st.column_config.NumberColumn("ID", format="%d"),
                       "abo_paternal": "From father", "abo_maternal": "From mother",
                       "birth_step": st.column_config.NumberColumn("Born (year)", format="%d")},
        alt="First 300 synthetic agents",
    )
    st.caption("First 300 of the synthetic agents. Founders' paternal/maternal order is randomised; all records are fabricated.")
    st.download_button("Download all agents (CSV)", data=lambda: agents.to_csv(index=False).encode(),
                       file_name=f"agents_seed{cfg.seed}.csv", mime="text/csv", icon=":material/download:")
