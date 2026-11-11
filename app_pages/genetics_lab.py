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


@st.cache_data(max_entries=48)
def _child_counts(p1: str, p2: str, n: int, seed: int) -> tuple[int, ...]:
    """Genotype counts for n births. Cached so the same parents and seed do not redraw from scratch."""
    rng = np.random.default_rng(seed)
    a1, a2 = genotype_to_codes(p1)
    b1, b2 = genotype_to_codes(p2)
    pat = transmit_alleles(np.full(n, a1, np.int8), np.full(n, a2, np.int8), rng)
    mat = transmit_alleles(np.full(n, b1, np.int8), np.full(n, b2, np.int8), rng)
    counts = np.bincount(GENOTYPE_LUT[pat, mat], minlength=6)
    return tuple(int(c) for c in counts)


@st.fragment
def _lab() -> None:
    with st.container(border=True):
        father, mother = st.columns(2, gap="medium")
        with father:
            st.pills(
                "Father's genotype", list(ABO_GENOTYPES), required=True, key="gl_p1", width="stretch", wrap=True,
                format_func=lambda g: f"{g} ({GENOTYPE_TO_PHENOTYPE[g]})", persist_state="session",
                help="The letters are the alleles. The group in brackets is what a blood test would report.",
            )
        with mother:
            st.pills(
                "Mother's genotype", list(ABO_GENOTYPES), required=True, key="gl_p2", width="stretch", wrap=True,
                format_func=lambda g: f"{g} ({GENOTYPE_TO_PHENOTYPE[g]})", persist_state="session",
                help="Same six genotypes. AA, BB and OO still have two alleles, so the square keeps two columns.",
            )

    p1, p2 = st.session_state.gl_p1, st.session_state.gl_p2
    left, right = st.columns([1, 1.35], gap="large")

    with left:
        with st.container(border=True):
            st.subheader(
                "Punnett square", icon=":material/grid_on:",
                help="Each cell is one of the four equally likely children.",
            )
            st.caption("Exact probabilities. No randomness.")
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
                + " · ".join(
                    f":{'blue' if k == 'A' else 'orange' if k == 'B' else 'violet' if k == 'AB' else 'green'}-badge[{k} {v:.0%}]"
                    for k, v in theory.items() if v > 0
                )
            )
            st.caption("Each cell is 25%. Genotypes are written AO, never OA.")

    with right:
        with st.container(border=True):
            st.subheader(
                "Simulate many births", icon=":material/casino:",
                help="Grey bars are the exact shares. Red bars are one random sample of children.",
            )
            n_col, seed_col = st.columns(2)
            n_col.select_slider(
                "Number of children", options=[100, 1_000, 10_000, 100_000], key="gl_n", persist_state="session",
                help="Small samples jump around the exact shares. Large samples sit on them.",
            )
            seed_col.number_input(
                "Random seed", 0, 10**9, key="gl_seed", persist_state="session",
                help="The same seed and the same parents give the same children.",
            )
            n, seed = int(st.session_state.gl_n), int(st.session_state.gl_seed)
            counts = np.array(_child_counts(p1, p2, n, seed))
            th = offspring_distribution(p1, p2)
            sim_label = f"Simulated (n = {n:,})"
            rows = []
            for i, g in enumerate(ABO_GENOTYPES):
                if th[g] > 0 or counts[i] > 0:
                    rows.append({"genotype": g, "series": "Theory", "share": th[g] * 100})
                    rows.append({"genotype": g, "series": sim_label, "share": counts[i] / n * 100})
            df = pd.DataFrame(rows)
            st.altair_chart(
                grouped_bars(
                    df, "genotype", "share", "series", {"Theory": "#6B6166", sim_label: "#B4234A"},
                    "Share of children (%)", fmt=".2f",
                ),
                alt=f"Simulated genotype shares of {n} children of {p1} x {p2} compared with theory",
            )
            exp = np.array([th[g] for g in ABO_GENOTYPES]) * n
            support = exp > 0
            impossible = int(counts[~support].sum())
            if support.sum() > 1:
                chi2, pval = stats.chisquare(counts[support], exp[support])
                verdict = "consistent with Mendel" if pval > 0.001 and impossible == 0 else "deviates from theory"
                st.markdown(
                    f"χ² = **{chi2:.2f}**, p = **{pval:.3f}**. Verdict: {verdict}. "
                    f"Impossible genotypes produced: **{impossible}**."
                )
                st.caption("A small p means this sample is a poor match to the exact shares. With a large n, p is usually not tiny.")
            else:
                only = ABO_GENOTYPES[int(np.argmax(exp))]
                st.markdown(f"Every child is **{only}**. Impossible genotypes produced: **{impossible}**.")
            badge("simulated")


_lab()

st.subheader("Try these", icon=":material/lightbulb:")
st.markdown(
    "- `AO × AO`: two group-A parents, and about 25% of the children are group **O**.\n"
    "- `AB × OO`: no AB or O children. About 50% A and 50% B.\n"
    "- `AA × BB`: every child is **AB**."
)
