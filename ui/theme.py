"""Shared visual vocabulary: fixed category colours and provenance labels."""
from __future__ import annotations

import streamlit as st

# Okabe-Ito based, colour-blind safe; identical meaning on every page.
PHENO_COLORS = {"A": "#0072B2", "B": "#E69F00", "AB": "#CC79A7", "O": "#009E73"}
GENO_COLORS = {"AA": "#004E7C", "AO": "#4FA3D9", "BB": "#A86F00", "BO": "#F2C45A", "AB": "#CC79A7", "OO": "#009E73"}
ALLELE_COLORS = {"A": "#0072B2", "B": "#E69F00", "O": "#009E73", "D": "#D55E00", "d": "#56B4E9"}
RH_COLORS = {"Rh+": "#D55E00", "Rh-": "#56B4E9"}
SCENARIO_COLORS = {
    "baseline": "#6B6166",
    "immigration": "#0072B2",
    "disease": "#D55E00",
    "bottleneck": "#CC79A7",
    "fitness": "#009E73",
}

PROVENANCE = {
    "observed": ("Observed reference", "blue", ":material/fact_check:",
                 "Published data with a cited source (here: Austrian health portal)."),
    "inferred": ("Inferred", "violet", ":material/functions:",
                 "Derived from observed data with a declared assumption (e.g. Hardy-Weinberg)."),
    "simulated": ("Simulated", "green", ":material/model_training:",
                  "Output of the agent-based model; depends on all assumptions."),
    "hypothetical": ("Hypothetical", "orange", ":material/science:",
                     "Scenario setting chosen by us (shock size, fitness effect); not evidence."),
    "synthetic": ("Synthetic demo", "gray", ":material/draft:",
                  "Illustrative numbers for teaching; never empirical Austria."),
}


def badge(kind: str) -> None:
    label, color, icon, help_ = PROVENANCE[kind]
    st.badge(label, icon=icon, color=color, help=help_)  # type: ignore[arg-type]


def badge_md(kind: str) -> str:
    label, color, _, _ = PROVENANCE[kind]
    return f":{color}-badge[{label}]"


def provenance_legend() -> None:
    with st.container(horizontal=True, gap="small"):
        for k in ("observed", "inferred", "simulated", "hypothetical", "synthetic"):
            badge(k)


def pct(x: float, digits: int = 1) -> str:
    return f"{x * 100:.{digits}f} %"
