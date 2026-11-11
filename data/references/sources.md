# Reference data sources

| reference_id | File | Kind | Status |
|---|---|---|---|
| `austria_gesundheitsportal_2022` | `austria_abo_rh.csv` | Observed (secondary source) | Attributed; **team must verify** before final report |
| `synthetic_demo` | `synthetic_demo.csv` | Synthetic / illustrative | Never label as Austria |

## austria_gesundheitsportal_2022

- **Publisher:** Gesundheitsportal Österreich (gesundheit.gv.at), the public health portal of the Austrian Federal Ministry of Social Affairs, Health, Care and Consumer Protection.
- **Page:** "Blutgruppenuntersuchung (BGR)", editorial team Gesundheitsportal, expert review listed on the page.
- **URL:** https://www.gesundheit.gv.at/labor/laborwerte/blutgruppenserologie-transfusion/blutgruppenuntersuchung
- **Last updated (per page):** 21 December 2022. **Accessed:** 11 November 2026.
- **Values:** A 41 %, B 15 %, AB 7 %, O 37 %; Rh-positive 81 %, Rh-negative 19 %.
- **Limitations:**
  - Whole-percent rounding.
  - Underlying sample (donors, patients, general population) and year not stated.
  - Marginal ABO and Rh distributions only; BloodTypeLab assumes ABO and RhD are independent (separate loci on chromosomes 9 and 1).
- **Better primary sources to look for:** Austrian Red Cross blood donation service (blut.at) donor statistics; published Austrian blood-donor typing studies.

Reference files are read-only. To add a dataset, create a new CSV with the same columns and register it in `bloodtypelab/reference.py`.
