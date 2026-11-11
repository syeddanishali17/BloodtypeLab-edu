import pandas as pd
import streamlit as st

from bloodtypelab.config import DemographyConfig
from bloodtypelab.demography import life_expectancy, net_reproduction_rate
from bloodtypelab.selection import PRESETS
from bloodtypelab.shocks import IMMIGRATION_SOURCES

st.title("Methods & references", icon=":material/menu_book:")
st.caption("Notes for explaining the model: the yearly loop, parameters, assumptions and sources.")

section = st.segmented_control(
    "Section", ["One simulated year", "Parameters", "Assumptions", "Open decisions", "Literature", "Limitations"],
    default="One simulated year", required=True, key="m_section", persist_state="session", label_visibility="collapsed",
    help="The yearly order, the numbers we chose and why, what is still open, and what the model does not claim.",
)

if section == "One simulated year":
    st.mermaid_chart(
        """
flowchart LR
  A["Start of year t<br/>living agents"] --> B["1 Immigration<br/>scheduled arrivals"]
  B --> C["2 Mortality<br/>ONE draw per agent<br/>q = 1-(1-q_age·fitness)(1-q_disease)(1-q_bottleneck)"]
  C --> D["3 Ageing<br/>survivors +1 year"]
  D --> E["4 Reproduction<br/>woman 15-49: P = f age × fecundity × K/N<br/>father: random eligible man"]
  E --> F["5 Inheritance<br/>allele 1 from father, allele 2 from mother<br/>optional mutation · Rh-HDN"]
  F --> G["6 Newborns age 0"]
  G --> H["7 Count + check<br/>N_end = N_start + imm + births - deaths"]
""",
        alt="Chronology of one simulated year",
    )
    st.markdown(
        """
**Why this order?** Deaths use the age at the start of the year (so infant mortality applies to last year's newborns),
survivors then age, and births happen last, so a newborn can never reproduce or be counted as a parent in its birth year.
A dead agent can never become a parent because parents are drawn only from survivors.

**Agent-based, but fast.** Every person is one row in NumPy arrays (sex, age, paternal/maternal ABO and RhD alleles,
birth year, sensitisation). Each rule is applied to each individual with its own random draw. That is the microscopic
model the brief recommends ("pick individuals, let them die or reproduce"), evaluated for all agents at once.

**Random numbers.** One seed spawns three independent streams (initialisation, dynamics, immigration). Same seed ⇒ identical
starting population in every scenario (*common random numbers*), which makes paired comparisons much sharper.
"""
    )
elif section == "Parameters":
    d = DemographyConfig()
    rows = [
        ("Time step", "1 year", "Design choice", "Brief requires equidistant steps; unit is ours"),
        ("Mortality q(x)", f"Gompertz-Makeham a={d.makeham_a}, b={d.gompertz_b}, c={d.gompertz_c}; q(0)={d.infant_mortality}; max age {d.max_age}",
         "Illustrative", f"Life expectancy ≈ {life_expectancy(d):.1f} y"),
        ("Fertility f(x)", f"Gaussian, mean {d.fertility_mean_age}, sd {d.fertility_sd}, ages {d.female_min_age}-{d.female_max_age}, TFR {d.tfr}",
         "Illustrative", f"R₀ ≈ {net_reproduction_rate(d):.2f} before regulation"),
        ("Fathers", f"Uniform among men {d.male_min_age}-{d.male_max_age} (weighted by fecundity if non-neutral)", "Simplification", "Random mating, as in the brief"),
        ("Regulation", "birth prob × (K/N)^η, K = N₀, η = 1", "Modelling device", "Phenotype-neutral; keeps N stable"),
        ("Sex ratio at birth", "50 % female", "Simplification", "Real ≈ 48.8 %"),
        ("ABO × Rh", "Independent loci", "Assumption", "Source gives marginals only"),
        ("Genotype inference", "Hardy-Weinberg EM (default)", "Inferred", "Residuals reported"),
        ("Mutation", "0 by default", "Extension", "Real rates ~1e-5 to 1e-6"),
    ]
    st.dataframe(pd.DataFrame(rows, columns=["Parameter", "Value", "Status", "Note"]), hide_index=True, alt="Parameter glossary")
    st.markdown("**Fitness presets**")
    st.dataframe(pd.DataFrame([{"Preset": v["title"], "Status": v["status"], "Meaning": v["description"]} for v in PRESETS.values()]),
                 hide_index=True, alt="Fitness presets")
    st.markdown("**Immigration source presets**")
    st.dataframe(pd.DataFrame([{"Source": v["title"], "p(A)": v["allele_freqs"]["A"], "p(B)": v["allele_freqs"]["B"],
                                "p(O)": v["allele_freqs"]["O"], "p(d)": v["rh_neg_allele"], "Status": v["status"]}
                               for v in IMMIGRATION_SOURCES.values()]), hide_index=True, alt="Immigration sources")
elif section == "Assumptions":
    st.markdown(
        """
| # | Assumption | Type | Consequence if wrong |
|---|---|---|---|
| A1 | Austrian shares A 41 / B 15 / AB 7 / O 37 %, Rh− 19 % (Gesundheitsportal 2022) | Observed, secondary | Different starting point; dynamics unaffected |
| A2 | Hardy–Weinberg equilibrium for hidden genotypes | Inferred | Carrier shares (AO, BO) shift; sensitivity via *explicit split* |
| A3 | ABO and RhD independent | Assumption | Combined types (e.g. O−) slightly off |
| A4 | Random mating, no assortative mating or population structure | Simplification | Drift and HWE behaviour differ |
| A5 | Illustrative mortality/fertility, stable population via regulation | Illustrative | Time scale of change; not frequencies' direction under neutrality |
| A6 | One child per woman per year max, no twins | Simplification | Negligible |
| A7 | Shock sizes and fitness effects | Hypothetical | Results are conditional on them |
| A8 | Closed population except explicit immigration | Design | No emigration flows |
"""
    )
elif section == "Open decisions":
    st.markdown(
        """
| Question for the supervisor | Our proposal |
|---|---|
| Executable Rh: is the brief's single-locus +/− model enough? | Yes, switchable; full Rh genetics only in the literature review |
| Mutation: random operator or biologically motivated? | Operator implemented, off by default; rate sweep as sensitivity |
| System boundary and time scale | Austria, closed + explicit migration shocks; 1-year steps, 100–300 years |
| Which fitness rules need literature support? | Neutral + labelled hypotheses; Rh-HDN as documented mechanism |
| Are immigration + disease acceptable as the two shocks? | Yes, plus a neutral bottleneck as control |
| Is a separate DES model expected? | No. The brief describes an ABM with equidistant steps. AnyLogic docking is there if we want a second implementation. |
| Validation evidence and hand-in format | Tests + replicates + sensitivity; report, code, slides; app as support |
"""
    )
elif section == "Literature":
    st.caption("Starter bibliography. Check every entry before citing it in the report.")
    st.markdown(
        """
- Landsteiner K. (1901). Discovery of the ABO groups. *Wiener klinische Wochenschrift* 14.
- Bernstein F. (1924/25). Multiple-allele inheritance of the ABO groups; gene-counting estimator.
- Yamamoto F. et al. (1990). Molecular genetic basis of the histo-blood group ABO system. *Nature* 345.
- Ségurel L. et al. (2012). The ABO blood group is a trans-species polymorphism in primates. *PNAS* 109.
- Wagner F.F., Flegel W.A. (2000). RHD gene deletion occurred in the Rhesus box. *Blood* 95.
- Levine P. et al. (1941). Iso-immunization in erythroblastosis fetalis (haemolytic disease of the newborn).
- Rowe J.A. et al. (2007). Blood group O protects against severe *P. falciparum* malaria (reduced rosetting). *PNAS* 104.
- Ellinghaus D. et al. (2020). GWAS of severe Covid-19 with respiratory failure (ABO locus). *NEJM* 383.
- Grimm V. et al. (2020). The ODD protocol for agent-based models, second update. *JASSS* 23(2).
- Axtell R. et al. (1996). Aligning simulation models: a case study and results ("docking"). *Comput. Math. Organ. Theory* 1.

**Caution:** the brief's "O first, then A and B by mutation" is a simplification. Common O alleles are loss-of-function
variants of the A/B glycosyltransferase gene, and the ABO polymorphism predates the human lineage.
"""
    )
else:
    st.markdown(
        """
- **Not a forecast.** Demography is illustrative; shocks and fitness effects are hypothetical.
- **Not medical advice.** No claim is made about any individual's disease risk.
- **Simplified genetics.** ABO subgroups (A1/A2), RHD variants (weak/partial D) and RHCE are ignored.
- **Finite populations drift.** Small or zero differences between scenarios are legitimate results, not errors.
- **Historical origin not reconstructed.** Starting from today's frequencies cannot reproduce how A, B and O arose.
- **Reference data** are rounded marginals from a secondary source; the team must verify them before the final report.
"""
    )
