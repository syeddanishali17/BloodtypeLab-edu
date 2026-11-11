# BloodTypeLab

An agent-based model of ABO and RhD blood types, plus a Streamlit app that runs it.

The public app is [https://bloodtypelab-edu.streamlit.app/](https://bloodtypelab-edu.streamlit.app/).

Each simulated person carries two ABO alleles and two RhD alleles. Every year some people die, the survivors get one year older, and some women have a child. The child takes one allele at random from each parent. We start from the published Austrian blood-group shares and ask what can move them: chance, a difference in survival or births, or an outside shock such as immigration or a disease that hits one blood group.

The model is the Python package `bloodtypelab/`. The app (`app.py`) is a way to run it, compare scenarios and export the tables. It does not replace the code or a written report. The people in a run are synthetic. The output is not a forecast and not medical advice.

## What we are trying to do

1. Read the literature on how ABO and Rhesus types evolved, and keep a short bibliography we can actually check (`docs/literature_review.md`, and the Methods page).
2. Build a population that starts from the Austrian shares, then try rules for how blood type might affect fitness (survival or births).
3. Compare at least two outside shocks with a run that has no shock.
4. Write the results down so someone else can repeat them: config, seed, and the files the app exports.

## Why it is built this way

**We see blood groups, but children inherit alleles.** "41% group A" does not say how many of those people are `AA` and how many are `AO`. Only the alleles are passed on. The default assumption is Hardy-Weinberg equilibrium, which is the usual way to go from blood groups back to allele frequencies when mating is random. The published percents are rounded, so the fit is not exact. The app shows that gap instead of hiding it. You can also ignore Hardy-Weinberg and type the AA / AO split yourself.

**A finite population wanders even when nothing is selecting.** That wandering is genetic drift. A shock or a fitness rule only counts as an effect if it moves the shares more than this noise. That is why comparisons use several runs, and why every scenario in one comparison uses the same seeds. Seed 7 builds the same starting population in the baseline and in the immigration run, so the difference is not "we happened to start with more B".

**The brief asks for individuals, not a single equation for the whole country.** Each person has their own age, sex and alleles, and their own random draws for death, birth and which allele they pass on. The code stores those people in NumPy arrays and updates them together, which is much faster than a Python loop over objects. It is still one record per person. A dead person is never chosen as a parent.

**Shocks interact with age.** A disease that kills mostly old people barely changes what the next generation inherits. A disease that kills young adults does. You only see that if people have ages. The mortality and fertility curves are illustrative (Gompertz-Makeham mortality, a bell-shaped fertility schedule, total fertility rate 2.1). They are not fitted to Statistik Austria. Births are also pulled back toward the starting population size, and that pull does not depend on blood group. Without it, the population would grow or shrink for decades and the frequency plots would be hard to read.

## One simulated year

For each year, in this order:

1. Add any immigrants scheduled for that year. Their genotypes are drawn from the source allele frequencies.
2. Each living person gets one death draw. Age, a fitness multiplier, a disease and a bottleneck can all enter that probability.
3. Survivors age by one year.
4. Each woman aged 15-49 may have at most one child. The father is a random man aged 15-64. The child gets one random allele from the father and one from the mother. Mutation is optional and off by default. Rh incompatibility can drop a pregnancy, and that is also off unless you turn it on.
5. Newborns join at age 0. They cannot be parents in the year they are born.
6. Counts are checked. Population must equal last year plus immigrants plus births minus deaths. Allele counts must be twice the number of people. If a check fails, the run stops.

Deaths use the age at the start of the year, so last year's babies can still die as infants. "Disease deaths" in the charts are the extra deaths, not everyone who happened to die while a disease was switched on.

Phenotypes: `AA` and `AO` are group A, `BB` and `BO` are group B, `AB` is AB, `OO` is O. `DD` and `Dd` are Rh+, `dd` is Rh-. Genotype strings are stored in one order (`AO`, never `OA`).

## Starting numbers

`data/references/austria_abo_rh.csv` uses A 41%, B 15%, AB 7%, O 37%, Rh+ 81%, Rh- 19%. Source: Gesundheitsportal Österreich, page updated 21 Dec 2022. The page gives the two margins separately, so the model treats ABO and Rh as independent.

The Hardy-Weinberg fit of those rounded ABO shares is about p(A) = 0.278, p(B) = 0.117, p(O) = 0.605. In that fit, most people with group A are `AO`, which is why two group-A parents can have a group-O child. Sex is 50/50. Ages follow the stationary distribution of the mortality table. There is a second reference, `synthetic_demo`, which is fake and labelled as such.

## Fitness and shocks

Fitness presets multiply survival or birth rates by blood group. Neutral is the control: every multiplier is 1. The other presets are hypothetical. The exception is Rh incompatibility (haemolytic disease of the newborn): the mechanism is real, the probability in the app is not taken from a data set.

Shocks:

- **Immigration.** A chosen number of people per year, for a chosen number of years, from a source allele mix. The "high B" and "high O" sources are made up.
- **Disease.** For a few years, chosen blood groups (and optionally only Rh+ or Rh-) get a higher death risk. A relative risk on the age hazard mostly hits older people. An extra death probability hits every age.
- **Bottleneck.** One year of extra deaths that ignore blood type. If the bottleneck moves the shares as much as the disease, the disease result was mostly "the population got smaller", which is drift.

Mutation of an ABO allele exists and defaults to probability 0. Real rates are around 10^-5 to 10^-6 per generation, which you will not see in a few hundred years. Turning the rate up is only for teaching.

## How to read a result

Comparisons are paired. The same seeds are used in every scenario, the difference is taken seed by seed, and then we average. The band on a chart is the 2.5 to 97.5 percentile across those runs. It is the spread of the runs, not a confidence interval for the mean. If the band of a difference includes 0, this experiment did not separate the effect from drift.

Charts use percent. Differences of shares are in percentage points (pp). CSV files store shares as fractions between 0 and 1. Each run has an id and a manifest with the full config, the seed, the reference file hash, and hashes of the output files.

## The app

Eight pages in the sidebar, in one list. Hover a page name for a one-line description. Most inputs have a `?` tooltip. Badges mark where a number came from: observed, inferred, simulated, hypothetical, or synthetic. Hover the badge.

| Page | What you do there |
|---|---|
| Overview | The question, the Austrian starting shares, and a short path through the other pages |
| Genetics lab | Pick two parents. The Punnett square is the exact 2 by 2. The chart next to it is many random births against those exact shares, with a chi-square check |
| Population explorer | Turn the reference shares into genotypes and then into people. Shows the residual of the Hardy-Weinberg fit, the hidden carriers, ages, and a slice of the agent table |
| Simulation studio | One run. Settings on the left are a draft. The plot on the right is the last run that finished. Changing a slider does not change that plot until you press Run. A failed run keeps the previous result |
| Scenario comparison | Baseline plus the shocks you tick, several seeds, bands, and a table at any year |
| Validation & evidence | Runs the checks in the session. A tick appears only after the check has run |
| AnyLogic bridge | Downloads a zip (agents, tables, a Java model) and compares an uploaded CSV with repeated Python runs from the same start |
| Methods & references | The yearly order, the parameter list, assumptions, open questions, a short bibliography |

The sidebar remembers the last completed simulation: scenario, seed, size, and whether the yearly checks passed.

Colours for A, B, AB, O, Rh and the scenarios are the same on every page, and they are chosen so they are not only distinguished by red versus green. Charts have text alternatives. Light and dark theme both work. Nothing runs until you press a button, except the Genetics lab, which is cheap enough to update as you change the parents.

## Run it locally

Tested with Python 3.12 on Windows.

```bat
setup_windows.bat
run_local.bat
```

`setup_windows.bat` creates `.venv` if it is missing, installs the pinned packages and runs a short test. `run_local.bat` opens http://127.0.0.1:8501 and binds to localhost.

By hand:

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m streamlit run app.py --server.address 127.0.0.1
```

On macOS or Linux the interpreter is `.venv/bin/python`.

No database, login or API key. The theme tries to load the Inter font. Offline, the browser uses a system font.

Without the browser:

```bash
python scripts/run_baseline.py --config data/demo/demo_config.json
python scripts/run_experiments.py --replicates 20 --fitness o_survival_advantage
python scripts/export_anylogic_bundle.py --out anylogic_bundle
```

## Put it on Streamlit Community Cloud

It is already deployed: [https://bloodtypelab-edu.streamlit.app/](https://bloodtypelab-edu.streamlit.app/).

Community Cloud builds that URL from this GitHub repo (`syeddanishali17/BloodtypeLab-edu`, branch `main`, file `app.py`, Python 3.12). A push to `main` does not always show up immediately. On [share.streamlit.io](https://share.streamlit.io), open the app and choose **Reboot** after a theme or `requirements.txt` change. A code-only change is usually picked up by the next deploy.

To create the same app again:

1. Sign in at https://share.streamlit.io with the GitHub account that owns the repo.
2. Choose **Create app**. Pick the repository, branch `main`, and main file `app.py`.
3. Set the Python version to **3.12**. The code was tested on 3.12.
4. Leave secrets empty. There is no API key. Do not add `.venv` or `results/`. They are gitignored.
5. Deploy. The first build installs `requirements.txt` (Streamlit, Altair, NumPy, pandas, SciPy). Pytest is in that file and is unused at runtime. The build takes a few minutes.
6. Open the app. In Genetics lab, set a parent to `AA`, `BB` or `OO`. The Punnett square should render. Then run a small simulation (a few hundred agents, 20 years) so you know the free instance can finish a run.

Cloud limits memory and CPU. A comparison with 5,000 agents, 150 years and 30 replicates can stall or get cut off. For a public demo, keep the default population or smaller, and use about 10 replicates. Long jobs still belong on your own machine, via the scripts above.

`run_local.bat` passes `--server.address 127.0.0.1` so the laptop app is not exposed on the network. That flag is not in `.streamlit/config.toml`, so Cloud can bind the port itself.

## AnyLogic

AnyLogic does not run these Python agents. The bridge writes a zip of the starting agents, the rate tables and a Java model. You can run that model in AnyLogic, or with Java 11+ on its own, and upload the yearly counts. The app then compares them with Python runs that started from the same agents. See `anylogic/README.md` and `docs/anylogic_integration.md`.

## Layout

```text
app.py                  navigation and sidebar
app_pages/              the eight pages
ui/                     charts, shared controls, session state
bloodtypelab/           the model (no Streamlit imports)
  genetics.py           ABO / RhD, inheritance, mutation, Hardy-Weinberg
  engine.py             the yearly loop
  initialization.py     starting population
  demography.py         mortality, fertility
  selection.py          fitness presets
  shocks.py             immigration, disease, bottleneck
  experiments.py        paired replicates
  exports.py            CSV, manifest, zip
  anylogic_bridge.py    bundle and docking test
data/references/        Austrian figures and a synthetic demo set
scripts/                baseline, experiments, AnyLogic export
tests/
docs/                   model notes, assumptions, literature starter, report outline
```

The model package does not import Streamlit. A finished run is not edited in place. A failed run does not replace the last good one. Reference CSVs are read only.

## Limits

- Demography, shock sizes and most fitness effects are hypothetical.
- The Austrian figures are rounded secondary numbers. A primary donor series would be better before a final write-up. See `data/references/sources.md`.
- No A1/A2 subgroups, no weak D, no population structure, no emigration.
- Open questions are listed in the app under Methods, and in `docs/decisions_from_supervisor.md`.

## What is included, and what is not

The model and the app are original code. `LICENSE` is the MIT license, copyright SyedDanishAli, 2026.

The Austrian blood-group figures are a few published percentages, with the page title, URL and the date they were read. See `data/references/sources.md`. The health-portal page is not copied into the repo.

The bibliography names papers by author and year. The papers themselves are not included. Inter and JetBrains Mono are used as fonts under the SIL Open Font License. The theme loads them from Google Fonts. If that request is blocked, the browser falls back to a system font.

Two slide files were taken out of the repository. They contained a stock picture of blood cells, and there is no licence on file for that picture. Screenshots of this app can be made again from a running session.

This is a student project. It is not an official product of a university or of Gesundheitsportal Österreich.

## Sources

- Gesundheitsportal Österreich, *Blutgruppenuntersuchung (BGR)*, https://www.gesundheit.gv.at/labor/laborwerte/blutgruppenserologie-transfusion/blutgruppenuntersuchung (updated 21 Dec 2022, accessed 11 Nov 2026).
- Short bibliography, still to be checked before citing: `docs/literature_review.md`.
