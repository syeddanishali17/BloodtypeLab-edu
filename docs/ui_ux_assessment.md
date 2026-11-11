# Frontend UI/UX assessment

Assessment of the BloodTypeLab Streamlit app (v0.2.0, Streamlit 1.67) against established usability heuristics
(Nielsen's 10 heuristics), scientific-visualisation practice and WCAG accessibility basics. Scores: ● strong,
◐ adequate, ○ weak. Verified by headless app tests (`tests/test_app_smoke.py`) and by manual inspection in light and
dark mode at desktop and narrow widths.

## 1. Usability heuristics

| Heuristic | Score | Evidence | Remaining gap |
|---|---|---|---|
| Visibility of system status | ● | progress bars with "year t of H" / "run k of n", toasts, sidebar card with the last completed run and invariant badge | no cancel button for long batches (Streamlit runs are synchronous) |
| Match with the real world | ● | domain words (phenotype, allele, carrier, shock); Punnett square; percentages and percentage points | — |
| User control and freedom | ● | explicit run buttons; draft settings never alter finished runs; save/load configuration; recent-runs table | no undo for "load configuration" |
| Consistency and standards | ● | same colours for A/B/AB/O/Rh/scenarios on every page; same control block reused (Studio and Comparison) | — |
| Error prevention | ● | bounded inputs, validation before running, resource guard (agent-years), Rh-only options hidden when Rh is off | — |
| Recognition rather than recall | ● | presets with descriptions; shocks described in plain text; tooltips on pages and inputs | — |
| Flexibility and efficiency | ◐ | defaults run in one click; headless scripts for power users | no keyboard shortcuts |
| Aesthetic and minimalist design | ● | wide layout, settings left / results right; advanced settings in expanders; segmented view switcher | Studio settings column is long when all shocks are on |
| Help users recover from errors | ● | `st.error` with title and actionable message; previous result kept and labelled | — |
| Help and documentation | ● | Overview demo path, Methods page, captions under every chart, README | — |

## 2. Scientific-visualisation practice

| Practice | Score | Evidence |
|---|---|---|
| Provenance visible | ● | Observed / Inferred / Simulated / Hypothetical / Synthetic badges; source link and dates |
| Uncertainty shown and named | ● | "mean + empirical 2.5–97.5 % band", paired differences, explanation when the band contains 0 |
| Correct units | ● | % on charts, fractions in CSV, "pp" for differences |
| Annotations of interventions | ● | shocks drawn as shaded spans + dashed rules with tooltips |
| Direct labelling | ◐ | line charts labelled at the end; stacked areas rely on legend + tooltip |
| Theory vs simulation distinguished | ● | Genetics lab bars "Theory" vs "Simulated (n = …)" with χ² |
| No chartjunk | ● | Altair defaults following the theme; no 3-D, no dual axes |

## 3. Accessibility (WCAG-oriented)

| Item | Score | Evidence | Gap |
|---|---|---|---|
| Colour-blind-safe palette | ● | Okabe–Ito colours for categories | — |
| Not colour alone | ◐ | labels, legends, tooltips, text tables | stacked areas need the legend |
| Text alternatives | ● | `alt=` on every chart, table and diagram | — |
| Contrast / themes | ● | custom light **and** dark themes, user can toggle | contrast not machine-audited |
| Keyboard navigation | ◐ | native Streamlit widgets are keyboard accessible | charts are mouse-oriented |
| Responsive | ◐ | sidebar collapses, columns stack on narrow screens | dense tables scroll horizontally on phones (desktop-first by spec) |

## 4. Streamlit-specific best practices applied

- `st.navigation` + `st.Page` with sections, Material icons and help text (instead of the legacy `pages/` folder).
- Theme in `.streamlit/config.toml` (fonts, radii, palettes, light/dark, sidebar) — no CSS injection.
- `persist_state="session"` keeps draft settings when switching pages; defaults seeded once in session state.
- Expensive work only behind buttons; view switches use `st.segmented_control` (cheap reruns, no hidden tab work).
- Deferred download data (`data=lambda: …`) so ZIPs are built only when clicked.
- Sentence-case labels, `st.metric(border=True, chart_data=…)` KPI cards with sparklines.
- Headless `AppTest` tests for every page and main action.

## 5. Recommended next improvements

1. Add a "Cancel" via `st.fragment` + background thread for batches above ~60 s.
2. Direct end-labels on stacked area charts.
3. A one-click "presentation mode" that loads the demo configuration on each page.
4. Automated contrast check of both themes.
