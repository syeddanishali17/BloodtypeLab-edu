# Model specification (ODD protocol)

Structured after the ODD protocol (Grimm et al. 2020). Implementation: `bloodtypelab/`, version 0.2.0.

## 1. Purpose and patterns
Explain how Mendelian inheritance, demographic stochasticity, phenotype-dependent fitness and external shocks change
the ABO and RhD distribution of a population initialised from Austrian reference data. Patterns used for evaluation:
Mendelian ratios in crosses; stable frequencies (only drift) under neutrality; Hardy–Weinberg heterozygosity maintained
under random mating; plausible life expectancy and stable population size.

## 2. Entities, state variables and scales
- **Person** (agent): `agent_id`, `sex`, `age`, `abo_paternal`, `abo_maternal`, `rh_paternal`, `rh_maternal`,
  `birth_step`, `rh_sensitized`.
- **Population** (global): list of living agents, ID counter, carrying capacity K.
- **Environment**: none spatial; time-dependent shock schedule.
- **Scales**: time step 1 year; horizon 1–1000 years (typically 100–300); population 2–200 000 agents.

## 3. Process overview and scheduling
Per year t: (1) immigration, (2) mortality — one Bernoulli draw per agent with combined probability, (3) ageing,
(4) reproduction incl. inheritance, mutation and Rh-HDN, (5) newborns added at age 0, (6) observation and invariant
checks. Agents are processed synchronously within each sub-step (order-independent because each agent's draw is
independent).

## 4. Design concepts
- **Basic principles**: Mendel's law of segregation; codominance/recessiveness; Hardy–Weinberg for initial genotypes.
- **Emergence**: phenotype/allele frequency trajectories emerge from individual births and deaths.
- **Adaptation / objectives / learning / prediction / sensing**: none (agents do not decide).
- **Interaction**: mating (random partner of the opposite sex among eligible survivors); density regulation through N.
- **Stochasticity**: deaths, births, partner choice, allele transmission, sex of newborns, mutation, immigrant
  genotypes/ages, initial genotypes/sex/ages.
- **Collectives**: none.
- **Observation**: counts per year (phenotype, genotype, allele, Rh, combined types), births, deaths by cause,
  immigrants, fetal losses, mutations, mean age, observed and HWE-expected heterozygosity.

## 5. Initialisation
Reference shares → HWE allele frequencies (EM; alternatives Bernstein, explicit split) → N agents by multinomial
sampling or quotas; founders' paternal/maternal order randomised; sex Bernoulli(0.5); ages from the stationary
distribution l(x)/Σl(x) of the mortality schedule. RhD independent with d = √(Rh− share).

## 6. Input data
`data/references/austria_abo_rh.csv` (observed, secondary source) or `synthetic_demo.csv`. Shock schedule from the
configuration. No time-series input.

## 7. Submodels

| Submodel | Equation |
|---|---|
| Baseline mortality | μ(x) = a + b·e^{cx}, q(x) = 1 − e^{−μ(x)}, q(0) = q₀, q(x_max) = 1 |
| Fitness on survival | q' = 1 − (1 − q)^{RR(phenotype)} |
| Disease (relative risk) | q'' = 1 − (1 − q')^{RR_d} for affected agents |
| Disease (additional) | q'' = 1 − (1 − q')(1 − p_d) |
| Bottleneck | q_tot = 1 − (1 − q'')(1 − f) |
| Fertility | P(birth) = min(1, f(age) · w(phenotype) · (K/N)^η), f Gaussian scaled to TFR |
| Partner choice | father ~ uniform (or ∝ w) over men aged 15–64 |
| Inheritance | allele₁ ~ U{father's two alleles}, allele₂ ~ U{mother's two alleles} |
| Mutation | with prob μ, allele → other allele (uniform or user matrix) |
| Rh-HDN | if mother dd, child Rh+, mother sensitised: loss with prob p_hdn; Rh+ pregnancy sensitises mother |
| Immigration | genotypes ~ HWE(source p, q, r), d; ages ~ U[a_min, a_max]; sex Bernoulli(0.5) |

Parameter defaults and status: `docs/assumptions_register.md`.
