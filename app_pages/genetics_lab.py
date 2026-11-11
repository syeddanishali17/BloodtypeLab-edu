import numpy as np
import pandas as pd
import streamlit as st
from scipy import stats

from bloodtypelab.genetics import (
    ABO_GENOTYPES,
    GENOTYPE_LUT,
    GENOTYPE_TO_PHENOTYPE,
    genotype_to_codes,
    offspring_distribution,
    offspring_phenotype_distribution,
    punnett_square,
    transmission_labels,
    transmit_alleles,
)
from ui.charts import grouped_bars
from ui.theme import badge

st.title("Genetics lab", icon=":material/genetics:")
st.caption("Mendel's first law in the ABO system: each parent passes one of its two alleles, chosen at random.")

st.session_state.setdefault("gl_p1", "AO")
st.session_state.setdefault("gl_p2", "BO")
st.session_state.setdefault("gl_n", 10_000)
st.session_state.setdefault("gl_seed", 1)

with st.container(border=True):
    c1, c2 = st.columns(2)
    c1.pills("Father's genotype", list(ABO_GENOTYPES), required=True, key="gl_p1",
             format_func=lambda g: f"{g} ({GENOTYPE_TO_PHENOTYPE[g]})", persist_state="session")
    c2.pills("Mother's genotype", list(ABO_GENOTYPES), required=True, key="gl_p2",
             format_func=lambda g: f"{g} ({GENOTYPE_TO_PHENOTYPE[g]})", persist_state="session")

p1, p2 = st.session_state.gl_p1, st.session_state.gl_p2
left, right = st.columns([1, 1.4], gap="large")

with left:
    st.subheader("Punnett square", icon=":material/grid_on:")
    st.caption("Theoretical expectation (exact probabilities, no randomness).")
    sq = punnett_square(p1, p2)
    table = pd.DataFrame(
        [[f"{g} ({GENOTYPE_TO_PHENOTYPE[g]})" for g in row] for row in sq],
        index=transmission_labels(p1, "Father"),
        columns=transmission_labels(p2, "Mother"),
    )
    st.table(table, alt=f"Punnett square for {p1} x {p2}")
    theory = offspring_phenotype_distribution(p1, p2)
    st.markdown(
        "**Expected children:** "
        + " · ".join(f":{'blue' if k=='A' else 'orange' if k=='B' else 'violet' if k=='AB' else 'green'}-badge[{k} {v:.0%}]"
                     for k, v in theory.items() if v > 0)
    )
    st.caption("Each cell has probability 25 %. Genotypes are written canonically (AO, never OA).")

with right:
    st.subheader("Simulate many births", icon=":material/casino:")
    c1, c2 = st.columns(2)
    c1.select_slider("Number of children", options=[100, 1_000, 10_000, 100_000], key="gl_n", persist_state="session")
    c2.number_input("Random seed", 0, 10**9, key="gl_seed", persist_state="session")
    n, seed = int(st.session_state.gl_n), int(st.session_state.gl_seed)
    rng = np.random.default_rng(seed)
    a1, a2 = genotype_to_codes(p1)
    b1, b2 = genotype_to_codes(p2)
    pat = transmit_alleles(np.full(n, a1, np.int8), np.full(n, a2, np.int8), rng)
    mat = transmit_alleles(np.full(n, b1, np.int8), np.full(n, b2, np.int8), rng)
    counts = np.bincount(GENOTYPE_LUT[pat, mat], minlength=6)
    th = offspring_distribution(p1, p2)
    sim_label = f"Simulated (n = {n:,})"
    rows = []
    for i, g in enumerate(ABO_GENOTYPES):
        if th[g] > 0 or counts[i] > 0:
            rows.append({"genotype": g, "series": "Theory", "share": th[g] * 100})
            rows.append({"genotype": g, "series": sim_label, "share": counts[i] / n * 100})
    df = pd.DataFrame(rows)
    st.altair_chart(
        grouped_bars(df, "genotype", "share", "series", {"Theory": "#6B6166", sim_label: "#B4234A"},
                     "Share of children (%)", fmt=".2f"),
        alt=f"Simulated genotype shares of {n} children of {p1} x {p2} compared with theory",
    )
    exp = np.array([th[g] for g in ABO_GENOTYPES]) * n
    support = exp > 0
    impossible = int(counts[~support].sum())
    if support.sum() > 1:
        chi2, pval = stats.chisquare(counts[support], exp[support])
        verdict = "consistent with Mendel" if pval > 0.001 and impossible == 0 else "deviates from theory"
        st.markdown(
            f"χ² = **{chi2:.2f}**, p = **{pval:.3f}**. Verdict: {verdict}. Impossible genotypes produced: **{impossible}**."
        )
        st.caption("Small samples bounce around the 25 % cells. That same sampling noise is what shows up as genetic drift in a small population.")
    else:
        st.markdown(f"Deterministic cross: every child is **{ABO_GENOTYPES[int(np.argmax(exp))]}**. Impossible genotypes produced: **{impossible}**.")
    badge("simulated")

st.subheader("Try these", icon=":material/lightbulb:")
st.markdown(
    "- `AO × AO`: two group-A parents, and about 25 % of the children are group **O** (hidden carriers).\n"
    "- `AB × OO`: the A and O alleles never meet in one child, so there are **no AB or O** children. About 50 % A, 50 % B.\n"
    "- `AA × BB`: every child is **AB**. A and B are both expressed."
)
