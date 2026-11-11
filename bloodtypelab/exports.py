"""Structured, immutable exports: CSV tables, manifest with hashes, validation summary, ZIP."""
from __future__ import annotations

import hashlib
import io
import json
import os
import platform
import shutil
import zipfile
from pathlib import Path

import numpy as np

from . import __version__
from .config import SCHEMA_VERSION
from .engine import RunResult
from .metrics import long_table, population_table

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.ndarray,)):
        return o.tolist()
    if isinstance(o, (set, tuple)):
        return list(o)
    raise TypeError(f"Not JSON serialisable: {type(o)}")


def run_tables(run: RunResult) -> dict[str, "object"]:
    """Name -> DataFrame for the documented export contract."""
    rid, sc, seed = run.run_id, run.scenario, run.seed
    tables = {
        "population_timeseries.csv": population_table(run.timeseries, rid, sc, seed),
        "phenotype_timeseries.csv": long_table(run.timeseries, "phenotype", rid, sc, seed),
        "genotype_timeseries.csv": long_table(run.timeseries, "genotype", rid, sc, seed),
        "allele_timeseries.csv": long_table(run.timeseries, "allele", rid, sc, seed),
        "agents_start_sample.csv": run.agents_start,
        "agents_end_sample.csv": run.agents_end,
    }
    if run.config.include_rh:
        tables["rh_timeseries.csv"] = long_table(run.timeseries, "rh", rid, sc, seed)
        tables["blood_type_timeseries.csv"] = long_table(run.timeseries, "blood_type", rid, sc, seed)
    return tables


def validation_summary(run: RunResult) -> dict:
    from .validation import validate_run

    rep = validate_run(run)
    return {
        "run_id": run.run_id,
        "passed": rep.passed,
        "checks": [c.as_dict() for c in rep.checks],
        "invariant_failures": run.invariant_failures,
        "warnings": run.warnings,
    }


def manifest(run: RunResult, files: dict[str, str] | None = None) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "model_version": __version__,
        "run_id": run.run_id,
        "status": run.status,
        "created_utc": run.created_utc,
        "scenario": run.scenario,
        "seed": run.seed,
        "config_hash": run.config_hash,
        "config": run.config.to_dict(),
        "reference": run.reference,
        "initialization": run.inference,
        "initial_comparison": run.initial_comparison,
        "elapsed_seconds": round(run.elapsed_seconds, 4),
        "extinct_step": run.extinct_step,
        "warnings": run.warnings,
        "invariants_ok": run.invariants_ok,
        "share_units": "fraction in [0, 1]; plots show percent",
        "environment": {"python": platform.python_version(), "numpy": np.__version__, "platform": platform.platform()},
        "files": files or {},
    }


def run_file_bytes(run: RunResult) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    for name, df in run_tables(run).items():
        out[name] = df.to_csv(index=False).encode("utf-8")
    out["validation_summary.json"] = json.dumps(validation_summary(run), indent=2, default=_json_default).encode()
    hashes = {k: hashlib.sha256(v).hexdigest() for k, v in out.items()}
    out["manifest.json"] = json.dumps(manifest(run, hashes), indent=2, default=_json_default).encode()
    out["config.json"] = run.config.to_json().encode()
    return out


def export_run(run: RunResult, directory: Path | str | None = None) -> Path:
    """Write ``<directory>/<run_id>/``. Written to ``.partial`` first and renamed when complete.

    Never overwrites an existing completed run folder.
    """
    base = Path(directory) if directory else RESULTS_DIR
    base.mkdir(parents=True, exist_ok=True)
    final = base / run.run_id
    if final.exists():
        raise FileExistsError(f"Run folder {final} already exists; completed runs are immutable.")
    partial = base / f"{run.run_id}.partial"
    if partial.exists():
        shutil.rmtree(partial)
    partial.mkdir()
    try:
        for name, data in run_file_bytes(run).items():
            (partial / name).write_bytes(data)
        os.replace(partial, final)
    except Exception:
        shutil.rmtree(partial, ignore_errors=True)
        raise
    return final


def zip_runs(runs: list[RunResult], extra: dict[str, bytes] | None = None) -> bytes:
    """In-memory ZIP of one folder per run (for browser download)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for run in runs:
            for name, data in run_file_bytes(run).items():
                zf.writestr(f"{run.run_id}/{name}", data)
        for name, data in (extra or {}).items():
            zf.writestr(name, data)
    return buf.getvalue()
