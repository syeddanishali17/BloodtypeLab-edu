# BloodTypeLab ↔ AnyLogic docking bundle

This folder (and the ZIP exported from the app's **AnyLogic bridge** page) lets you build an
**independent AnyLogic implementation** of the BloodTypeLab model and check that it agrees with
the Python model ("docking", Axtell et al. 1996).

## Files

| File | Content |
|---|---|
| `agents.csv` | Initial population: `agent_id,sex,age,abo_paternal,abo_maternal,rh_paternal,rh_maternal` |
| `parameters.csv` | `key,value,unit,status` (population, horizon, age windows, regulation, mutation, HDN) |
| `mortality_table.csv` | `age,q` annual death probability (q at max age = 1) |
| `fertility_table.csv` | `age,f` annual birth probability for women |
| `selection.csv` | `phenotype,survival_rr,fecundity` (A, B, AB, O, Rh+, Rh-) |
| `shocks.csv` | `shock_id,kind,start_step,duration_steps,param,value` |
| `anylogic_output_TEMPLATE.csv` | Header of the file AnyLogic must write |
| `java_snippets/*.java` | Person fields/functions, startup loader, yearly event |
| `config.json` | Full Python configuration (for the record) |

## Build steps (AnyLogic 8.x, any edition incl. PLE)

1. New model, time unit **years**.
2. Agent type **Person** with the parameters/variables in `Person_fields.java`; add the functions.
3. In **Main**: population `people` (Person, initially empty), the variables listed at the top of
   `Main_startup.java`, and paste that file into *Main → On startup*.
4. Add a cyclic **Event** `yearStep` (first occurrence 1, recurrence 1) with `Main_yearly_event.java`.
5. Add function `writeCounts()` (body at the end of the event file).
6. Copy the unzipped bundle folder next to the `.alp` file and run. Use a *Parameter Variation*
   experiment with ≥ 5 replications (fresh random seed each) for a proper statistical test.
7. Upload `anylogic_output.csv` on the **AnyLogic bridge** page.

## Rules that must match exactly

- Chronology: immigration → **one** death draw per agent (age at start of year) → ageing → births.
- Death probability with fitness: `q' = 1 - (1 - q)^RR`; extra risks combine as `1 - (1-q)(1-q_extra)`.
- Birth: each woman aged 15–49 at most one child per year with probability `f(age) × fecundity × (K/N)^η`.
- Father: uniform random man aged 15–64 (weighted by fecundity if non-neutral).
- Child: allele 1 from the father, allele 2 from the mother, each a fair coin flip between the parent's two alleles.
- Newborns age 0, cannot reproduce in their birth year.

## Interpreting the docking test

The app runs ≥ 20 Python replicates **from the same `agents.csv`** (same seed, different dynamics
seeds) and checks per phenotype that the AnyLogic mean trajectory stays within a
Bonferroni-corrected two-sample z bound at every year, plus a KS test on final shares when
AnyLogic has ≥ 5 replicates. A failure usually means a scheduling difference (e.g. ageing before
death), not a genetics bug.
