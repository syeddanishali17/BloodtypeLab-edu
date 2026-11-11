# AnyLogic integration guide

## Can we integrate AnyLogic?

Yes, in four ways (see README §9). AnyLogic cannot run our Python `Person` rows as AnyLogic agents, so any
integration either exchanges **files**, calls across **processes** (Pypeline, Alpyne) or uses the **cloud** API.
The scientifically valuable route is **docking**: two independent implementations of the same conceptual model,
started from identical agents, must produce statistically indistinguishable outputs. Disagreement reveals hidden
assumptions (usually scheduling) — that is model verification by replication.

## Workflow

1. In the app, configure and run a scenario in **Simulation studio**.
2. **AnyLogic bridge → Download AnyLogic bundle**. Unzip next to your `.alp` model.
3. Build the AnyLogic model with `anylogic/README.md` and `anylogic/java_snippets/` (Person agent, startup loader,
   yearly cyclic event, `writeCounts()`).
4. Run a Parameter Variation experiment with ≥ 5 replications; collect `anylogic_output.csv`
   (`replicate,step,population,n_A,n_B,n_AB,n_O,rh_pos`).
5. **AnyLogic bridge → upload** the CSV. The app runs 30 Python replicates from the same agents and reports:
   - fraction of years inside the Python 95 % band (descriptive),
   - max |z| of the two-sample z statistic over years vs a Bonferroni critical value,
   - KS test on final-year shares (≥ 5 AnyLogic replicates),
   - a verdict and overlay charts.

## Shocks in AnyLogic

Read `shocks.csv` on startup into a small list. In the yearly event:
- immigration: if `start ≤ step < start+duration`, add `count_per_step` Persons; draw each allele independently with
  probabilities `p_A, p_B, p_O` (HWE), Rh alleles with `p_rh_neg_allele`, age uniform in `[age_min, age_max]`;
- disease: for affected phenotypes multiply the hazard (`q = 1-(1-q)^RR`) or combine `q = 1-(1-q)(1-p)`;
- bottleneck: in that year combine every agent's `q` with the fraction.

## Pitfalls that break docking
- Ageing before the death draw (shifts mortality by one year).
- More than one death draw per agent per year.
- Allowing newborns to reproduce in their birth year.
- Using `randomFrom(people)` for fathers without filtering sex and age.
- Applying regulation with N after births instead of after deaths (the Python model uses N after deaths and ageing).

## Other levels
- **Pypeline** (AnyLogic library): call `bloodtypelab.reference.infer_genotype_frequencies` from AnyLogic to share the
  HWE inference; keep per-birth logic in Java for speed.
- **Alpyne**: drive an exported AnyLogic model from Python for parameter sweeps; check that your edition supports the
  required export first.
- **AnyLogic Cloud API**: possible, but needs an account, API key and network — conflicts with the local-first design.
