# BloodTypeLab

A local agent-based model of ABO and RhD blood types, with a Streamlit app to run it.

Each person has two ABO alleles and two RhD alleles. Every year some people die, everyone who is left gets a year older, and some women have a child. The child gets one allele at random from each parent. The starting point is the published Austrian blood-group distribution. The question is what can move that distribution: chance, a fitness difference, or a shock such as immigration or a disease that hits one blood group.

The model lives in `bloodtypelab/`. The app is `app.py`. Nothing here is a forecast or medical advice. The people in a run are synthetic.

## Run it

Tested with Python 3.12 on Windows.

```bat
setup_windows.bat
run_local.bat
```

That creates `.venv` if it is missing, installs the pinned packages, runs a short test, and opens http://127.0.0.1:8501.

By hand:

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m streamlit run app.py --server.address 127.0.0.1
```

On macOS or Linux the interpreter is `.venv/bin/python`.

No database, login, or API key. The app tries to load the Inter font; if that fails it uses a system font.

Headless runs:

```bash
python scripts/run_baseline.py --config data/demo/demo_config.json
python scripts/run_experiments.py --replicates 20 --fitness o_survival_advantage
python scripts/export_anylogic_bundle.py --out anylogic_bundle
```

## App pages

| Page | What it is for |
|---|---|
| Overview | The question, the yearly loop, the Austrian starting numbers |
| Genetics lab | Punnett square and a lot of simulated births, compared with the exact probabilities |
| Population explorer | Turn the reference shares into genotypes and a starting population |
| Simulation studio | One run: population, demography, fitness, mutation, shocks, export |
| Scenario comparison | Same seeds across baseline, immigration, disease, bottleneck, fitness |
| Validation & evidence | Checks you can run yourself, plus where the reference numbers came from |
| AnyLogic bridge | Export a bundle and compare an AnyLogic CSV with the Python runs |
| Methods & references | Order of events, parameters, assumptions, open questions, short bibliography |

## The model, briefly

An agent has an id, sex, age, two ABO alleles (A, B or O), two RhD alleles (D or d), a birth year, and a flag used only by the Rh incompatibility option.

Phenotypes: `AA` and `AO` are group A, `BB` and `BO` are group B, `AB` is AB, `OO` is O. `DD` and `Dd` are Rh+, `dd` is Rh-. Genotype strings are stored in a fixed order (`AO`, never `OA`).

One year, in this order:

1. Add any scheduled immigrants.
2. Each living person gets one death draw. Age, fitness, disease and a bottleneck can all enter that probability.
3. Survivors age by one year.
4. Women aged 15-49 may give birth (at most one child that year). The father is a random man aged 15-64. The child takes one random allele from each parent.
5. Newborns join at age 0. They cannot be parents in that same year.
6. Counts are checked. If the books do not balance, the run stops.

Deaths use the age at the start of the year, so last year's babies can still die as infants. A dead person is not drawn as a parent.

### Starting population

`data/references/austria_abo_rh.csv` uses A 41%, B 15%, AB 7%, O 37%, Rh+ 81%, Rh- 19% (Gesundheitsportal Österreich, updated 21 Dec 2022). ABO and Rh are treated as independent because the source only gives the two margins.

Those are phenotypes. Inheritance needs genotypes. The default is Hardy-Weinberg, fitted with the gene-counting EM algorithm. With the rounded Austrian figures that comes out near p(A) = 0.278, p(B) = 0.117, p(O) = 0.605. The fit does not match the published percents exactly (they are rounded). The gap is shown in the app. You can also use Bernstein's estimator, or type the AA/AO split yourself.

About 81% of group-A people in that fit are `AO`, so two group-A parents can have a group-O child.

Sex is 50/50. Ages come from the stationary distribution of the mortality table.

### Demography and fitness

Mortality is a Gompertz-Makeham curve plus a separate infant risk, with death certain at 105. Fertility is a bell curve from 15 to 49, scaled to a total fertility rate of 2.1. Births are also multiplied by (K/N), with K equal to the starting size, so the population does not explode or die out and swamp the frequency plots. These numbers are illustrative. They are not a fit to Statistik Austria.

Fitness presets change survival or birth rates by phenotype. They are labelled as hypothetical, except the Rh incompatibility option, which is a known mechanism with a made-up probability. A neutral preset is the control. Mutation of ABO alleles exists and is off by default. Real rates are far too small to see in a few hundred years.

### Shocks

- Immigration: a chosen number of people per year, for a chosen number of years, drawn from a source allele frequency (the presets are hypothetical).
- Disease: for a few years, selected phenotypes get a higher death risk.
- Bottleneck: one year of extra deaths that ignore blood type. That is the "this is just drift" control.

Comparisons use the same seeds in every scenario, so the starting population matches. Plots show the mean and a 2.5-97.5% band across replicates. If that band for a difference includes 0, the run did not separate the effect from drift.

## Checks

`pytest` covers the genetics (fixed crosses such as `AA x BB`, and chi-square checks on the random ones), the Hardy-Weinberg fit, population accounting, identical output for the same seed, exports, and a headless pass over the app pages. The Validation page can run the same checks in the session. A passing test means the code did what the rules say. It does not mean the death rates or fitness numbers are true.

## AnyLogic

AnyLogic does not run these Python agents. The bridge writes a zip of the starting agents, the tables, and a Java model. You can run that model in AnyLogic, or with Java 11+ on its own, and upload the yearly counts. The app then compares them with repeated Python runs from the same start. See `anylogic/README.md` and `docs/anylogic_integration.md`.

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
anylogic/               Java snippets and a short build note
tests/
docs/                   model notes, assumptions, literature starter, report outline
```

The scientific code does not import Streamlit. A finished run is not edited in place. A failed run does not replace the last good one.

## Limits

- Demography, shock sizes and most fitness effects are hypothetical.
- The Austrian figures are rounded secondary numbers. A primary donor series would be better before a final write-up. See `data/references/sources.md`.
- No A1/A2, no weak D, no population structure, no emigration.
- Open questions for a supervisor are listed in the app (Methods) and in `docs/decisions_from_supervisor.md`.

## Sources

- Gesundheitsportal Österreich, *Blutgruppenuntersuchung (BGR)*, https://www.gesundheit.gv.at/labor/laborwerte/blutgruppenserologie-transfusion/blutgruppenuntersuchung (updated 21 Dec 2022, accessed 11 Nov 2026).
- Short bibliography, still to be checked before citing: `docs/literature_review.md`.
