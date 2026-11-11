"""Session-state helpers. Completed results are stored separately from draft widget values."""
from __future__ import annotations

import streamlit as st

HISTORY_LIMIT = 6


def init_state() -> None:
    st.session_state.setdefault("last_run", None)  # latest successful RunResult (immutable)
    st.session_state.setdefault("run_history", [])  # list[RunResult], newest first
    st.session_state.setdefault("last_error", None)
    st.session_state.setdefault("batch", None)  # latest successful BatchResult
    st.session_state.setdefault("population_preview", None)
    st.session_state.setdefault("verification", None)  # (timestamp, list[CheckResult])
    st.session_state.setdefault("pytest_output", None)
    st.session_state.setdefault("docking", None)
    st.session_state.setdefault("studio_config", None)  # last config the studio validated


def push_run(run) -> None:
    st.session_state.last_run = run
    hist = [r for r in st.session_state.run_history if r.run_id != run.run_id]
    st.session_state.run_history = [run, *hist][:HISTORY_LIMIT]
