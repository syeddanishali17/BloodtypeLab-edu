import streamlit as st

from bloodtypelab.reference import infer_genotype_frequencies, load_reference
from ui.theme import provenance_legend

ref = load_reference("austria_gesundheitsportal_2022")
inf = infer_genotype_frequencies(ref, "hwe_em")

st.title("BloodTypeLab", icon=":material/bloodtype:")
st.markdown(
    "An **agent-based simulation** of how ABO and RhD blood types are inherited and how their distribution "
    "in a population can change over time, through chance, fitness differences and external shocks."
)

with st.grid(5, min_column_width=180):
    for p in ("A", "B", "AB", "O"):
        st.metric(
            f"Group {p}", f"{ref.abo[p] * 100:.0f} %", border=True, height="stretch",
            help=f"Austrian share of group {p}. {ref.source_label}, updated {ref.source_updated}.",
        )
    st.metric(
        "Rh-negative", f"{ref.rh['Rh-'] * 100:.0f} %", border=True, height="stretch",
        help=f"Austrian share of Rh-negative. {ref.source_label}.",
    )
st.caption(f"Observed reference: [{ref.source_label}]({ref.source_url}).")
st.caption(f"Updated {ref.source_updated}. Accessed {ref.accessed}.")

left, right = st.columns([1.15, 1], gap="large")
with left:
    st.subheader("The problem", icon=":material/help:",
                help="Blood group is what a lab reports. Children inherit alleles, and two people with the same blood group can carry different alleles.")
    st.markdown(
        "Every person carries **two alleles** for the ABO blood group, one from the father and one from the mother. "
        "A and B are codominant, O is recessive, so four phenotypes appear: **A, B, AB, O**. RhD works the same way "
        "with **+ dominant over −**. The assignment asks how such a system *evolves* in a population starting from "
        "today's Austrian distribution."
    )
    st.markdown(
        """
| Task | What the brief asks | Where in this app |
|---|---|---|
| 1 · Literature | Evolution of blood types & Rhesus factor | Methods & references, `docs/literature_review.md` |
| 2 · Evolutionary model | Start from Austria; find how blood type influences **fitness** | Population explorer, Simulation studio (fitness rules) |
| 3 · External shocks | ≥ 2 shock types vs a **no-shock baseline** | Scenario comparison (immigration, disease, bottleneck) |
| 4 · Protocol | Document findings | Exports + manifests feed the written report |
"""
    )
with right:
    st.subheader("Our solution in one picture", icon=":material/account_tree:")
    st.mermaid_chart(
        """
flowchart TD
  R["Austrian reference<br/>A 41 · B 15 · AB 7 · O 37 %"] --> I["Hardy-Weinberg inference<br/>hidden genotypes"]
  I --> P["Synthetic population<br/>one record per person"]
  P --> Y{{"Each simulated year"}}
  Y --> S1["1 Immigration shock?"]
  S1 --> S2["2 Death draw<br/>age + fitness + disease"]
  S2 --> S3["3 Ageing"]
  S3 --> S4["4 Births<br/>1 allele from each parent"]
  S4 --> M["5 Count & check invariants"]
  M --> Y
  M --> O["Compare scenarios<br/>with replicates"]
""",
        alt="Model flow: reference data, genotype inference, synthetic population, yearly loop of immigration, death, ageing, births and metrics.",
    )

st.subheader("Genotype is not phenotype", icon=":material/visibility_off:")
c1, c2, c3 = st.columns(3)
with c1.container(border=True, height="stretch"):
    st.markdown("**What we observe**")
    st.markdown("Phenotype shares: A, B, AB, O. Someone with group **A** can be `AA` or `AO`. We cannot see which.")
with c2.container(border=True, height="stretch"):
    st.markdown("**What we infer**")
    gf = inf.genotype_freqs
    st.markdown(
        f"Under Hardy–Weinberg: allele O ≈ **{inf.allele_freqs['O']:.3f}**, A ≈ **{inf.allele_freqs['A']:.3f}**, "
        f"B ≈ **{inf.allele_freqs['B']:.3f}**. So ≈ {gf['AO'] / (gf['AA'] + gf['AO']):.0%} of Austrians with group A are `AO` carriers."
    )
with c3.container(border=True, height="stretch"):
    st.markdown("**Why it matters**")
    st.markdown("Two group-A parents can have a group-O child (`AO × AO`). Hidden O carriers make the O allele persist.")

st.subheader("Demo path for the instructor (5–7 min)", icon=":material/route:")
steps = [
    ("app_pages/genetics_lab.py", ":material/genetics:", "1 · Genetics lab", "Punnett square AO × BO and 10 000 simulated births vs theory."),
    ("app_pages/population.py", ":material/groups:", "2 · Population explorer", "Austria → genotypes → 5 000 agents; target vs realised."),
    ("app_pages/simulation.py", ":material/play_circle:", "3 · Simulation studio", "150-year neutral baseline, then add a shock."),
    ("app_pages/comparison.py", ":material/compare_arrows:", "4 · Scenario comparison", "Replicated, paired baseline vs shocks with uncertainty bands."),
    ("app_pages/validation.py", ":material/verified:", "5 · Validation", "Run the verification suite live. Nothing is ticked before the check has run."),
    ("app_pages/anylogic.py", ":material/sync_alt:", "6 · AnyLogic bridge", "Docking test: does an independent model agree?"),
]
grid = st.columns(3)
for i, (path, icon, label, text) in enumerate(steps):
    with grid[i % 3].container(border=True, height="stretch"):
        st.page_link(path, label=label, icon=icon, width="stretch")
        st.caption(text)

st.subheader("How to read every number in this app", icon=":material/label:",
            help="Hover a badge. Observed means a published figure. Inferred means we calculated it. Simulated means the model produced it. Hypothetical means we chose the scenario. Synthetic means the people are not real.")
provenance_legend()
st.caption(
    "Hover a badge for its meaning. Demographic parameters are illustrative and uncalibrated; shock and fitness magnitudes "
    "are hypothetical. Outputs are implications of assumptions, **not** medical or demographic forecasts. All agents are synthetic."
)
