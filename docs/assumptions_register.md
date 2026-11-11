# Assumptions register

Status legend: **Observed** (cited data) · **Inferred** (derived with a declared assumption) · **Design** (modelling
choice) · **Illustrative** (placeholder value) · **Hypothetical** (scenario setting).

| ID | Assumption / parameter | Value | Status | Source / rationale | Sensitivity handle |
|---|---|---|---|---|---|
| A1 | Austrian ABO shares | A .41, B .15, AB .07, O .37 | Observed | Gesundheitsportal 2022 | Reference selector |
| A2 | Austrian Rh shares | Rh+ .81, Rh− .19 | Observed | same | Reference selector |
| A3 | ABO ⟂ RhD | independence | Design | different chromosomes; no joint data | — |
| A4 | Hidden genotypes | HWE (EM) | Inferred | standard population genetics | Bernstein / explicit split |
| A5 | Time step | 1 year | Design | brief: equidistant steps | — |
| A6 | Mortality | Gompertz–Makeham a=5e-4, b=1.6e-5, c=0.1, q₀=0.004, max 105 | Illustrative | e₀ ≈ 80 y | config |
| A7 | Fertility | Gaussian mean 30, sd 5.5, 15–49, TFR 2.1 | Illustrative | replacement level | TFR slider |
| A8 | Male reproductive ages | 15–64 | Illustrative | — | config |
| A9 | Mating | random among eligible | Design | brief | — |
| A10 | Density regulation | (K/N)^η, K=N₀, η=1 | Design | avoid growth/collapse confound | toggle + strength |
| A11 | Sex ratio at birth | 0.5 | Design | simplification (real ≈ 0.488) | config |
| A12 | Max one birth per woman per year | — | Design | no twins | — |
| A13 | Fitness presets | see `selection.py` | Hypothetical | literature-motivated only for HDN mechanism | presets / custom |
| A14 | Immigration sources | see `shocks.py` | Hypothetical | — | presets |
| A15 | Disease effects | RR or extra probability | Hypothetical | no medical claim | sliders |
| A16 | Mutation | μ = 0 | Design | real rates negligible on horizon | number input |
| A17 | No emigration, closed otherwise | — | Design | system boundary Austria | — |

Changes to any row must be recorded here with date and reason, and reflected in `decisions_from_supervisor.md` if
the supervisor requested them.
