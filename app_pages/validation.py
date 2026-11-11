import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from bloodtypelab.reference import available_references, infer_genotype_frequencies, load_reference
from bloodtypelab.validation import run_verification_suite, validate_run

ROOT = Path(__file__).resolve().parent.parent

st.title("Validation & evidence", icon=":material/verified:")
st.caption(
    "Two different questions. **Verification:** did we implement the rules we intended? **Validation:** do those rules "
    "support the scientific claim? Nothing on this page shows a pass before the check has actually run."
)

verif_tab, cred_tab = st.columns(2, gap="large")

with verif_tab:
    st.subheader("Code verification", icon=":material/rule:")
    st.markdown(
        "Mendelian crosses with χ² tests, canonical genotypes, invalid-input rejection, mutation-off control, "
        "Hardy–Weinberg inference recovery, reproducibility, zero-magnitude shocks, accounting invariants under all shocks, "
        "and a neutral-drift trend test."
    )
    quick = st.toggle("Quick mode (smaller samples)", value=False, key="val_quick")
    if st.button("Run verification suite", type="primary", icon=":material/play_arrow:"):
        with st.spinner("Running checks…"):
            t0 = time.perf_counter()
            checks = run_verification_suite(n_births=10_000 if quick else 20_000, quick=quick)
            st.session_state.verification = (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), checks, time.perf_counter() - t0)

    if st.session_state.verification is None:
        st.info("Not run yet in this session.", icon=":material/pending:")
    else:
        stamp, checks, secs = st.session_state.verification
        n_pass = sum(c.passed for c in checks)
        m1, m2, m3 = st.columns(3)
        m1.metric("Checks passed", f"{n_pass} / {len(checks)}", border=True)
        m2.metric("Run at", stamp.split(" ")[1], border=True, help=stamp)
        m3.metric("Duration", f"{secs:.1f} s", border=True)
        if n_pass == len(checks):
            st.success("All verification checks passed in this session.", icon=":material/check_circle:")
        else:
            st.error(f"{len(checks) - n_pass} check(s) failed. See the table.", icon=":material/error:")
        df = pd.DataFrame([c.as_dict() for c in checks])
        st.dataframe(
            df[["passed", "category", "name", "expected", "observed", "detail", "seconds"]], hide_index=True, height=440,
            alt="Verification check results",
            column_config={"passed": st.column_config.CheckboxColumn("Pass"),
                           "seconds": st.column_config.NumberColumn("s", format="%.2f")},
        )
        st.download_button("Download results (CSV)", df.to_csv(index=False).encode(), "verification_results.csv",
                           "text/csv", icon=":material/download:")

    with st.expander("Run the full pytest suite", icon=":material/terminal:"):
        st.caption("Runs `python -m pytest -q` in the project folder (about 10–20 s) and shows the real console output.")
        if st.button("Run pytest", icon=":material/bug_report:"):
            with st.spinner("pytest running…"):
                proc = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT,
                                      capture_output=True, text=True, timeout=600)
                st.session_state.pytest_output = (datetime.now().strftime("%H:%M:%S"), proc.returncode, proc.stdout[-6000:] + proc.stderr[-2000:])
        if st.session_state.pytest_output:
            when, code, out = st.session_state.pytest_output
            (st.success if code == 0 else st.error)(f"pytest exit code {code} at {when}")
            st.code(out, language="text")

with cred_tab:
    st.subheader("Scientific credibility", icon=":material/school:")
    st.markdown("**Data provenance**")
    rows = []
    for rid, meta in available_references().items():
        ref = load_reference(rid)
        inf = infer_genotype_frequencies(ref, "hwe_em")
        rows.append({"reference": ref.title, "kind": ref.kind, "source": ref.source_label, "updated": ref.source_updated,
                     "HWE max residual (pp)": inf.max_abs_residual * 100, "sha256": ref.file_sha256[:12]})
    st.dataframe(pd.DataFrame(rows), hide_index=True, alt="Reference datasets and provenance",
                 column_config={"HWE max residual (pp)": st.column_config.NumberColumn(format="%.2f")})
    st.caption("Residual = how far Hardy-Weinberg-implied phenotype shares are from the (rounded) reference. Reported, never hidden.")

    st.markdown("**Last completed run**")
    run = st.session_state.last_run
    if run is None:
        st.caption("No run yet. Run one in *Simulation studio* to see its run-level checks here.")
    else:
        rep = validate_run(run)
        st.caption(f"`{run.run_id}`")
        st.dataframe(pd.DataFrame([c.as_dict() for c in rep.checks])[["passed", "name", "observed"]], hide_index=True,
                     alt="Run-level checks", column_config={"passed": st.column_config.CheckboxColumn("Pass")})

    st.markdown("**Replicate variability (last comparison)**")
    batch = st.session_state.batch
    if batch is None or batch.baseline not in batch.runs:
        st.caption("No comparison yet. The spread of the neutral baseline across seeds shows how much change drift alone produces.")
    else:
        finals = [r.shares().share_a_O.iloc[-1] - r.shares().share_a_O.iloc[0] for r in batch.runs[batch.baseline]]
        s = pd.Series(finals) * 100
        st.metric("Baseline O-allele change: mean ± sd", f"{s.mean():+.2f} ± {s.std():.2f} pp", border=True,
                  help="Under neutrality the mean should be close to 0; the sd is the drift 'noise floor' any shock effect must exceed.")

    st.markdown("**What the tests cannot show**")
    st.markdown(
        "- Passing tests show the code follows the stated rules. They do not show that the demographic or fitness assumptions are true.\n"
        "- Demography is illustrative; Austrian calibration (Statistik Austria) is future work.\n"
        "- Shock and fitness magnitudes are hypothetical; results are *implications of assumptions*.\n"
        "- Independent cross-check: re-implement in AnyLogic and use the **AnyLogic bridge** docking test."
    )
