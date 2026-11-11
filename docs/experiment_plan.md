# Experiment plan

All experiments: Austrian reference, HWE-EM initialisation, illustrative demography with regulation, 1-year steps,
paired seeds (`default_seeds(n, 20261111)`), report mean and 2.5–97.5 % band of paired differences.

| ID | Question | Scenarios | Size | Output |
|---|---|---|---|---|
| E0 | Neutral behaviour and drift noise floor | baseline | N ∈ {1 000, 3 000, 10 000}, 300 y, 30 reps | SD of allele change vs N |
| E1 | Immigration (Task 3) | baseline vs high-B source, 10 %/20 %/50 % of N once, year 30 | 3 000, 150 y, 30 reps | Δ shares over time |
| E2 | Disease (Task 3) | baseline vs A-specific: RR 3/5/10 (5 y) and extra p 2 %/5 % (5 y) | 3 000, 150 y, 30 reps | Δ shares; transient vs lasting |
| E3 | Drift control | bottleneck 30 %/50 %/80 % | 3 000, 150 y, 30 reps | band width vs baseline |
| E4 | Fitness (Task 2) | survival RR sweep (0.8–1.2) vs fecundity sweep (0.9–1.1) for one phenotype | 3 000, 300 y, 30 reps | time to detectable change |
| E5 | Rh incompatibility | HDN p ∈ {0.05, 0.1, 0.3} | 5 000, 300 y, 30 reps | d-allele trajectory |
| E6 | Sensitivity of start | EM vs Bernstein vs explicit split (AA share 0.1–0.5) | 3 000, 150 y, 20 reps | final shares |
| E7 | Demography sensitivity | TFR 1.5/2.1/2.5 with/without regulation | 3 000, 150 y, 20 reps | N(t), shares |
| E8 | Docking (optional) | AnyLogic re-implementation of baseline + one shock | bundle size, ≥ 5 AnyLogic reps | docking report |

Run from the app (*Scenario comparison*) or headless (`scripts/run_experiments.py`). Archive each experiment folder
(manifests contain seeds and config hashes) and cite the folder name in the report figure captions.
