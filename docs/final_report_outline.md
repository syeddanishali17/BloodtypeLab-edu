# Final report outline (written protocol, Task 4)

Deadline: 8 February 2027. Presentation: 22 January 2027, 12:10–16:00.

1. **Abstract** (problem, method, key findings, limitations — 150 words)
2. **Introduction and objectives** — the four tasks; research questions
3. **Literature review** (Task 1) — ABO genetics and molecular basis; evolution of ABO (trans-species polymorphism,
   O as loss-of-function); RhD genetics and the RHD deletion; selection evidence (malaria, cholera, norovirus,
   COVID-19 GWAS); maternal–fetal incompatibility; population distributions incl. Austria
4. **Model description** (ODD, `docs/model_specification.md`) incl. event chronology figure
5. **Data and initialisation** — Austrian reference, HWE inference, residuals, target vs realised start
6. **Demographic and fitness assumptions** — assumptions register table
7. **Shocks and experiment design** — paired replicates, metrics, uncertainty definition
8. **Verification** — test list and results (pytest output, live suite)
9. **Validation** — neutral behaviour, HWE heterozygosity, sensitivity, optional docking
10. **Results** — E0–E7 with figures (each caption: experiment folder, seeds, model version)
11. **Discussion** — migration vs selection vs drift; post-reproductive mortality; limits of inference
12. **Conclusion**
13. **Appendix** — reproducibility (commands, configs), group contributions

Every figure must be reproducible from a manifest (`results/<run_id>/manifest.json`).
