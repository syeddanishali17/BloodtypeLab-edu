"""Reusable parameter controls. They only build validated config objects; no model logic here."""
from __future__ import annotations

from dataclasses import replace

import streamlit as st

from bloodtypelab.config import DemographyConfig, MutationConfig, ShockConfig, SimulationConfig
from bloodtypelab.demography import life_expectancy, net_reproduction_rate
from bloodtypelab.genetics import ABO_PHENOTYPES, RH_PHENOTYPES
from bloodtypelab.reference import available_references
from bloodtypelab.selection import PRESETS, custom_selection, preset
from bloodtypelab.shocks import IMMIGRATION_SOURCES, bottleneck_shock, disease_shock, immigration_shock

PERSIST = "session"
INIT_METHODS = {
    "hwe_em": "Hardy-Weinberg (EM, max. likelihood)",
    "hwe_bernstein": "Hardy-Weinberg (Bernstein)",
    "explicit_split": "Explicit split (sensitivity)",
}


def _k(prefix: str, name: str) -> str:
    return f"{prefix}_{name}"


DEFAULTS: dict[str, object] = {
    "reference": "austria_gesundheitsportal_2022",
    "n": 5000,
    "seed": 20261111,
    "years": 150,
    "rh": True,
    "init": "hwe_em",
    "alloc": "multinomial",
    "aa": 0.3,
    "bb": 0.1,
    "tfr": 2.1,
    "reg": True,
    "regs": 1.0,
    "sel": "neutral",
    "hdn": 0.0,
    "mu": 0.0,
    "use_imm": False,
    "use_dis": False,
    "use_bn": False,
    "imm_src": "high_b_source",
    "imm_start": 30,
    "imm_dur": 1,
    "imm_n": 1000,
    "imm_age": (18, 40),
    "dis_ph": ["A"],
    "dis_rh": [],
    "dis_mode": "relative_risk",
    "dis_rr": 5.0,
    "dis_x": 0.05,
    "dis_start": 30,
    "dis_dur": 5,
    "bn_f": 0.5,
    "bn_start": 30,
    **{f"rr_{p}": 1.0 for p in ABO_PHENOTYPES},
    **{f"fe_{p}": 1.0 for p in ABO_PHENOTYPES},
}


def init_defaults(prefix: str, **overrides: object) -> None:
    """Seed widget state once per session (widgets then take their value from session state only)."""
    for name, value in {**DEFAULTS, **overrides}.items():
        st.session_state.setdefault(_k(prefix, name), value)


def _clamp(prefix: str, names: tuple[str, ...], horizon: int) -> None:
    for n in names:
        key = _k(prefix, n)
        if key in st.session_state and int(st.session_state[key]) > horizon:
            st.session_state[key] = horizon


def model_settings(prefix: str) -> SimulationConfig:
    """Population, reference, demography, fitness and mutation controls -> base SimulationConfig."""
    refs = available_references()
    st.selectbox(
        "Reference distribution",
        list(refs),
        format_func=lambda r: refs[r]["title"],
        key=_k(prefix, "reference"),
        persist_state=PERSIST,
        help="Starting blood-type distribution. The Austrian reference is sourced; the synthetic demo is not empirical.",
    )
    c1, c2 = st.columns(2)
    c1.number_input(
        "Initial population", min_value=100, max_value=100_000, step=500,
        key=_k(prefix, "n"), persist_state=PERSIST, help="Number of agents (virtual people) at year 0.",
    )
    c2.number_input(
        "Base seed", min_value=0, max_value=2**31 - 1, step=1, key=_k(prefix, "seed"),
        persist_state=PERSIST, help="Same seed + same settings = identical result.",
    )
    st.slider("Years to simulate", 10, 500, step=10, key=_k(prefix, "years"), persist_state=PERSIST,
              help="One step is one year. 100 to 150 years is enough to see a shock. Selection on old-age survival is still hard to see at 300 years.")
    st.toggle("Simulate RhD (+/-) as well", key=_k(prefix, "rh"), persist_state=PERSIST,
              help="Single-locus RhD model described in the brief: + dominant over -.")

    with st.expander("Initial genotypes", icon=":material/functions:"):
        st.segmented_control("Inference method", list(INIT_METHODS), format_func=INIT_METHODS.get,
                             required=True, key=_k(prefix, "init"), persist_state=PERSIST,
                             help="How hidden genotypes are filled in from blood groups. EM and Bernstein are two Hardy-Weinberg fits. Explicit split is for checking how much the result depends on that guess.")
        st.segmented_control("Allocation", ["multinomial", "quota"], required=True,
                             format_func={"multinomial": "Random sampling", "quota": "Exact quotas"}.get,
                             key=_k(prefix, "alloc"), persist_state=PERSIST,
                             help="Exact quotas remove sampling noise from the starting population.")
        if st.session_state.get(_k(prefix, "init")) == "explicit_split":
            st.slider("Share of phenotype A that is AA", 0.0, 1.0, step=0.05, key=_k(prefix, "aa"), persist_state=PERSIST,
                      help="Of everyone who looks like group A, this fraction is AA. The rest are AO and can pass O to a child.")
            st.slider("Share of phenotype B that is BB", 0.0, 1.0, step=0.05, key=_k(prefix, "bb"), persist_state=PERSIST,
                      help="Of everyone who looks like group B, this fraction is BB. The rest are BO.")

    with st.expander("Demography (illustrative)", icon=":material/groups:"):
        st.slider("Total fertility rate (children per woman)", 0.0, 4.0, step=0.05, key=_k(prefix, "tfr"), persist_state=PERSIST,
                  help="Average number of children a woman would have if she lived through the fertile ages. 2.1 is near replacement. The curve is illustrative, not an Austrian life table.")
        st.toggle("Density regulation towards initial size", key=_k(prefix, "reg"), persist_state=PERSIST,
                  help="Birth probability x (K/N)^strength. Phenotype-neutral; keeps N stable so frequency changes are not confounded with growth.")
        if st.session_state.get(_k(prefix, "reg"), True):
            st.slider("Regulation strength", 0.0, 3.0, step=0.1, key=_k(prefix, "regs"), persist_state=PERSIST,
                      help="How hard births are pushed back toward the starting size. 0 turns it off. 1 is the default. It does not favour any blood group.")
        demo = DemographyConfig(
            tfr=float(st.session_state.get(_k(prefix, "tfr"), 2.1)),
            regulation=bool(st.session_state.get(_k(prefix, "reg"), True)),
            regulation_strength=float(st.session_state.get(_k(prefix, "regs"), 1.0)),
        )
        st.caption(
            f"Life expectancy ≈ {life_expectancy(demo):.1f} years · net reproduction rate R₀ ≈ "
            f"{net_reproduction_rate(demo):.2f} (before regulation) · Gompertz-Makeham mortality, Gaussian fertility 15-49."
        )

    with st.expander("Fitness rules (Task 2)", icon=":material/science:"):
        options = [*PRESETS, "custom"]
        st.selectbox("Selection preset", options, format_func=lambda p: PRESETS[p]["title"] if p in PRESETS else "Custom (hypothetical)",
                     key=_k(prefix, "sel"), persist_state=PERSIST,
                     help="A fitness rule changes survival or births by blood group. Neutral is the control. The other presets are labelled hypothetical, except Rh incompatibility, which is a known mechanism with a made-up probability.")
        sel_name = st.session_state.get(_k(prefix, "sel"), "neutral")
        if sel_name in PRESETS:
            st.caption(PRESETS[sel_name]["description"])
            selection = preset(sel_name)
        else:
            st.caption("Relative risk multiplies the annual death hazard; fecundity multiplies birth / partner-choice probability.")
            surv, fec = {}, {}
            cols = st.columns(4)
            for col, p in zip(cols, ABO_PHENOTYPES):
                surv[p] = col.number_input(f"Death RR {p}", 0.0, 5.0, step=0.01, key=_k(prefix, f"rr_{p}"), persist_state=PERSIST,
                                            help=f"1 leaves group {p} unchanged. Below 1 they die less often. Above 1 they die more often. This scales the age-specific hazard, so it mostly affects older people.")
                fec[p] = col.number_input(f"Fecundity {p}", 0.0, 5.0, step=0.01, key=_k(prefix, f"fe_{p}"), persist_state=PERSIST,
                                          help=f"1 leaves group {p} unchanged. Above 1 they are more likely to have a child or to be chosen as the father.")
            hdn = st.slider("Rh-HDN pregnancy-loss probability", 0.0, 0.5, step=0.01, key=_k(prefix, "hdn"), persist_state=PERSIST,
                            help="Chance that a sensitised Rh-negative mother loses an Rh-positive pregnancy. 0 turns the mechanism off.")
            selection = custom_selection(surv, fec, hdn)

    with st.expander("Mutation (extension, off by default)", icon=":material/genetics:"):
        st.number_input("Mutation probability per transmitted allele", 0.0, 0.05, step=0.0005, format="%.4f",
                        key=_k(prefix, "mu"), persist_state=PERSIST,
                        help="Real per-locus rates are ~1e-5 to 1e-6 per generation: invisible on this horizon. Higher values are 'educational exaggerations'.")

    s = st.session_state
    return SimulationConfig(
        initial_population=int(s.get(_k(prefix, "n"), 5000)),
        horizon_steps=int(s.get(_k(prefix, "years"), 150)),
        seed=int(s.get(_k(prefix, "seed"), 20261111)),
        reference_id=s.get(_k(prefix, "reference"), "austria_gesundheitsportal_2022"),
        initialization_method=s.get(_k(prefix, "init"), "hwe_em"),
        allocation=s.get(_k(prefix, "alloc"), "multinomial"),
        explicit_split_aa_fraction=float(s.get(_k(prefix, "aa"), 0.3)),
        explicit_split_bb_fraction=float(s.get(_k(prefix, "bb"), 0.1)),
        include_rh=bool(s.get(_k(prefix, "rh"), True)),
        demography=demo,
        selection=selection,
        mutation=MutationConfig(rate=float(s.get(_k(prefix, "mu"), 0.0))),
    )


def immigration_controls(prefix: str, horizon: int) -> ShockConfig:
    _clamp(prefix, ("imm_start", "imm_dur"), horizon)
    st.selectbox("Source population", list(IMMIGRATION_SOURCES), format_func=lambda k: IMMIGRATION_SOURCES[k]["title"],
                 key=_k(prefix, "imm_src"), persist_state=PERSIST,
                 help="Where the newcomers' alleles are drawn from. The high-B and high-O presets are hypothetical, not a real country.")
    src = IMMIGRATION_SOURCES[st.session_state.get(_k(prefix, "imm_src"), "high_b_source")]
    f = src["allele_freqs"]
    st.caption(f"Allele frequencies A {f['A']:.2f} · B {f['B']:.2f} · O {f['O']:.2f} · Rh- allele {src['rh_neg_allele']:.2f}. Status: {src['status']}.")
    c1, c2, c3 = st.columns(3)
    start = c1.number_input("Start year", 1, horizon, key=_k(prefix, "imm_start"), persist_state=PERSIST,
                            help="First year the arrivals are added. They join before deaths and births that year.")
    dur = c2.number_input("Duration (years)", 1, horizon, key=_k(prefix, "imm_dur"), persist_state=PERSIST,
                          help="How many years in a row people arrive. 1 is a single wave.")
    count = c3.number_input("Immigrants per year", 0, 100_000, step=100, key=_k(prefix, "imm_n"), persist_state=PERSIST,
                            help="Headcount added each year of the wave. Compare it with the starting population.")
    ages = st.slider("Immigrant age range", 0, 100, key=_k(prefix, "imm_age"), persist_state=PERSIST,
                     help="Ages are drawn uniformly in this range. Young adults can still have children. Retirees mostly cannot.")
    return immigration_shock(st.session_state.get(_k(prefix, "imm_src"), "high_b_source"), int(start), int(count), int(dur), int(ages[0]), int(ages[1]))


def disease_controls(prefix: str, horizon: int, include_rh: bool) -> ShockConfig:
    _clamp(prefix, ("dis_start", "dis_dur"), horizon)
    st.pills("Affected ABO phenotypes", list(ABO_PHENOTYPES), selection_mode="multi",
             key=_k(prefix, "dis_ph"), persist_state=PERSIST,
             help="Blood groups that take the extra risk. Leave others untouched.")
    if include_rh:
        st.pills("Restrict to Rh status (optional)", list(RH_PHENOTYPES), selection_mode="multi",
                 key=_k(prefix, "dis_rh"), persist_state=PERSIST,
                 help="Optional extra filter. Empty means every Rh status of the chosen blood groups.")
    st.segmented_control("Effect type", ["relative_risk", "additional_probability"], required=True,
                         format_func={"relative_risk": "Relative risk on hazard", "additional_probability": "Extra death probability"}.get,
                         key=_k(prefix, "dis_mode"), persist_state=PERSIST,
                         help="Relative risk mostly kills older people, so the allele frequencies often recover. An extra death probability hits every age, including people who have not had children yet.")
    mode = st.session_state.get(_k(prefix, "dis_mode"), "relative_risk")
    rr, extra = 1.0, 0.0
    if mode == "relative_risk":
        rr = st.slider("Relative risk (x annual hazard)", 0.0, 30.0, step=0.5, key=_k(prefix, "dis_rr"), persist_state=PERSIST,
                       help="1 is no change. 5 means five times the usual age-specific death hazard for the chosen groups, during the shock years only.")
    else:
        extra = st.slider("Extra annual death probability", 0.0, 0.5, step=0.01, key=_k(prefix, "dis_x"), persist_state=PERSIST,
                          help="Added chance of dying each shock year, on top of normal mortality, for every affected person regardless of age.")
    c1, c2 = st.columns(2)
    start = c1.number_input("Start year", 1, horizon, key=_k(prefix, "dis_start"), persist_state=PERSIST)
    dur = c2.number_input("Duration (years)", 1, horizon, key=_k(prefix, "dis_dur"), persist_state=PERSIST)
    st.caption(
        "Relative risk scales the age-specific hazard, so it mostly kills the old (little lasting evolutionary effect). "
        "An extra death probability hits all ages equally, including people still to have children."
    )
    affected = tuple(st.session_state.get(_k(prefix, "dis_ph")) or ())
    affected_rh = tuple(st.session_state.get(_k(prefix, "dis_rh")) or ()) if include_rh else ()
    return disease_shock(affected, int(start), int(dur), float(rr), mode, float(extra), affected_rh)


def bottleneck_controls(prefix: str, horizon: int) -> ShockConfig:
    _clamp(prefix, ("bn_start",), horizon)
    c1, c2 = st.columns(2)
    frac = c1.slider("Extra mortality (all phenotypes)", 0.0, 0.95, step=0.05, key=_k(prefix, "bn_f"), persist_state=PERSIST,
                     help="Chance of an extra death that year, the same for every blood group. 0.5 removes about half the population at random.")
    start = c2.number_input("Year", 1, horizon, key=_k(prefix, "bn_start"), persist_state=PERSIST,
                            help="The bottleneck lasts one year. Use it as the control next to a disease or a migration wave.")
    st.caption("Neutral control: removes people at random, so any lasting change is drift, not selection.")
    return bottleneck_shock(float(frac), int(start))


def apply_config_to_state(prefix: str, cfg: SimulationConfig) -> None:
    """Load a saved configuration into the widget keys (called from a callback before widgets render)."""
    s = st.session_state
    s[_k(prefix, "reference")] = cfg.reference_id
    s[_k(prefix, "n")] = cfg.initial_population
    s[_k(prefix, "seed")] = cfg.seed
    s[_k(prefix, "years")] = cfg.horizon_steps
    s[_k(prefix, "rh")] = cfg.include_rh
    s[_k(prefix, "init")] = cfg.initialization_method
    s[_k(prefix, "alloc")] = cfg.allocation
    s[_k(prefix, "aa")] = cfg.explicit_split_aa_fraction
    s[_k(prefix, "bb")] = cfg.explicit_split_bb_fraction
    s[_k(prefix, "tfr")] = cfg.demography.tfr
    s[_k(prefix, "reg")] = cfg.demography.regulation
    s[_k(prefix, "regs")] = cfg.demography.regulation_strength
    s[_k(prefix, "mu")] = cfg.mutation.rate
    if cfg.selection.preset in PRESETS and cfg.selection == preset(cfg.selection.preset):
        s[_k(prefix, "sel")] = cfg.selection.preset
    else:
        s[_k(prefix, "sel")] = "custom"
        for p in ABO_PHENOTYPES:
            s[_k(prefix, f"rr_{p}")] = cfg.selection.survival_rr[p]
            s[_k(prefix, f"fe_{p}")] = cfg.selection.fecundity[p]
        s[_k(prefix, "hdn")] = cfg.selection.hdn_loss_probability
    kinds = {sh.kind: sh for sh in cfg.shocks}
    s[_k(prefix, "use_imm")] = "immigration" in kinds
    s[_k(prefix, "use_dis")] = "disease" in kinds
    s[_k(prefix, "use_bn")] = "bottleneck" in kinds
    if "immigration" in kinds:
        sh = kinds["immigration"]
        src = next((k for k, v in IMMIGRATION_SOURCES.items() if v["allele_freqs"] == sh.source_allele_freqs), "high_b_source")
        s[_k(prefix, "imm_src")] = src
        s[_k(prefix, "imm_start")], s[_k(prefix, "imm_dur")], s[_k(prefix, "imm_n")] = sh.start_step, sh.duration_steps, sh.count_per_step
        s[_k(prefix, "imm_age")] = (sh.age_min, sh.age_max)
    if "disease" in kinds:
        sh = kinds["disease"]
        s[_k(prefix, "dis_ph")] = list(sh.affected_phenotypes)
        s[_k(prefix, "dis_rh")] = list(sh.affected_rh)
        s[_k(prefix, "dis_mode")] = sh.mode
        s[_k(prefix, "dis_rr")], s[_k(prefix, "dis_x")] = sh.relative_risk, sh.additional_probability
        s[_k(prefix, "dis_start")], s[_k(prefix, "dis_dur")] = sh.start_step, sh.duration_steps
    if "bottleneck" in kinds:
        sh = kinds["bottleneck"]
        s[_k(prefix, "bn_f")], s[_k(prefix, "bn_start")] = sh.fraction, sh.start_step


def config_summary(cfg: SimulationConfig) -> str:
    refs = available_references()
    parts = [
        f"{refs.get(cfg.reference_id, {}).get('title', cfg.reference_id)}",
        f"N₀ = {cfg.initial_population:,}",
        f"{cfg.horizon_steps} years",
        f"seed {cfg.seed}",
        f"init {cfg.initialization_method}",
        f"fitness: {PRESETS.get(cfg.selection.preset, {}).get('title', cfg.selection.preset)}",
    ]
    if cfg.mutation.rate:
        parts.append(f"mutation {cfg.mutation.rate:g}")
    if not cfg.include_rh:
        parts.append("ABO only")
    return " · ".join(parts)


def with_shocks(cfg: SimulationConfig, shocks: list[ShockConfig], scenario: str) -> SimulationConfig:
    return replace(cfg, shocks=tuple(shocks), scenario=scenario)
