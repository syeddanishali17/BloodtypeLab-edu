"""AnyLogic interoperability: file-based docking (model-to-model cross-validation).

Python exports everything an independent AnyLogic implementation needs to start from the
*same* initial population with the *same* rules; AnyLogic writes yearly counts back; this
module tests statistically whether the AnyLogic trajectories are consistent with the
Python replicate distribution (Axtell et al. 1996, "docking").
"""
from __future__ import annotations

import io
import hashlib
import zipfile
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from .config import SimulationConfig
from .demography import fertility_schedule, mortality_schedule
from .engine import RunResult, rng_streams, simulate
from .genetics import ABO_PHENOTYPES
from .initialization import initialize_population
from .reference import load_reference

ANYLOGIC_DIR = Path(__file__).resolve().parent.parent / "anylogic"
OUTPUT_COLUMNS = ["step", "population", "n_A", "n_B", "n_AB", "n_O", "rh_pos"]
REQUIRED_OUTPUT = ["step", "population", "n_A", "n_B", "n_AB", "n_O"]


def bundle_identity(config: SimulationConfig) -> str:
    """Identify the rules, initial seed and reference, independently of a replicate seed."""
    canonical = replace(config, dynamics_seed=None).to_json()
    reference_hash = load_reference(config.reference_id).file_sha256
    return hashlib.sha256((canonical + "\n" + reference_hash).encode()).hexdigest()


def bundle_files(config: SimulationConfig) -> dict[str, bytes]:
    """All files of the AnyLogic input bundle, as bytes."""
    config = config.validate()
    ref = load_reference(config.reference_id)
    rng_init, _, _ = rng_streams(config.seed)
    init = initialize_population(config, ref, rng_init)
    agents = init.population.to_frame(include_rh=True)[
        ["agent_id", "sex", "age", "abo_paternal", "abo_maternal", "rh_paternal", "rh_maternal"]
    ]
    d = config.demography
    params = [
        ("initial_population", config.initial_population, "people", "config"),
        ("horizon_steps", config.horizon_steps, "years", "config"),
        ("seed", config.seed, "-", "Python seed (AnyLogic uses its own RNG)"),
        ("include_rh", int(config.include_rh), "bool", "config"),
        ("female_min_age", d.female_min_age, "years", "illustrative"),
        ("female_max_age", d.female_max_age, "years", "illustrative"),
        ("male_min_age", d.male_min_age, "years", "illustrative"),
        ("male_max_age", d.male_max_age, "years", "illustrative"),
        ("max_age", d.max_age, "years", "illustrative"),
        ("sex_ratio_female", d.sex_ratio_female, "fraction", "illustrative"),
        ("regulation", int(d.regulation), "bool", "modelling device"),
        ("carrying_capacity", config.carrying_capacity, "people", "modelling device"),
        ("regulation_strength", d.regulation_strength, "-", "modelling device"),
        ("mutation_rate", config.mutation.rate, "per transmission", "extension"),
        ("hdn_loss_probability", config.selection.hdn_loss_probability, "per at-risk pregnancy", config.selection.status),
        ("bundle_id", bundle_identity(config), "sha256", "configuration and reference identity"),
    ]
    files: dict[str, bytes] = {}
    files["agents.csv"] = agents.to_csv(index=False).encode()
    files["parameters.csv"] = pd.DataFrame(params, columns=["key", "value", "unit", "status"]).to_csv(index=False).encode()
    q = mortality_schedule(d)
    f = fertility_schedule(d)
    files["mortality_table.csv"] = pd.DataFrame({"age": np.arange(q.size), "q": q}).to_csv(index=False).encode()
    files["fertility_table.csv"] = pd.DataFrame({"age": np.arange(f.size), "f": f}).to_csv(index=False).encode()
    sel = config.selection
    files["selection.csv"] = pd.DataFrame(
        {
            "phenotype": list(ABO_PHENOTYPES) + ["Rh+", "Rh-"],
            "survival_rr": [sel.survival_rr[p] for p in ABO_PHENOTYPES] + [sel.rh_survival_rr["Rh+"], sel.rh_survival_rr["Rh-"]],
            "fecundity": [sel.fecundity[p] for p in ABO_PHENOTYPES] + [sel.rh_fecundity["Rh+"], sel.rh_fecundity["Rh-"]],
        }
    ).to_csv(index=False).encode()
    matrix = config.mutation.matrix or ((0, .5, .5), (.5, 0, .5), (.5, .5, 0))
    files["mutation_matrix.csv"] = pd.DataFrame(matrix, columns=["A", "B", "O"], index=["A", "B", "O"]).to_csv(index_label="from").encode()
    shock_rows = []
    for i, s in enumerate(config.shocks):
        base = {"shock_id": i, "kind": s.kind, "start_step": s.start_step, "duration_steps": s.duration_steps}
        if s.kind == "immigration":
            for k, v in (("count_per_step", s.count_per_step), ("p_A", s.source_allele_freqs["A"]),
                         ("p_B", s.source_allele_freqs["B"]), ("p_O", s.source_allele_freqs["O"]),
                         ("p_rh_neg_allele", s.source_rh_neg_allele_freq), ("age_min", s.age_min), ("age_max", s.age_max)):
                shock_rows.append({**base, "param": k, "value": v})
        elif s.kind == "disease":
            shock_rows.append({**base, "param": "affected_phenotypes", "value": "|".join(s.affected_phenotypes)})
            shock_rows.append({**base, "param": "affected_rh", "value": "|".join(s.affected_rh)})
            shock_rows.append({**base, "param": "mode", "value": s.mode})
            shock_rows.append({**base, "param": "relative_risk", "value": s.relative_risk})
            shock_rows.append({**base, "param": "additional_probability", "value": s.additional_probability})
        else:
            shock_rows.append({**base, "param": "fraction", "value": s.fraction})
    files["shocks.csv"] = pd.DataFrame(
        shock_rows, columns=["shock_id", "kind", "start_step", "duration_steps", "param", "value"]
    ).to_csv(index=False).encode()
    files["anylogic_output_TEMPLATE.csv"] = (",".join(["replicate"] + OUTPUT_COLUMNS + ["bundle_id"]) + "\n").encode()
    files["config.json"] = config.to_json().encode()
    readme = ANYLOGIC_DIR / "README.md"
    if readme.exists():
        files["README_ANYLOGIC.md"] = readme.read_bytes()
    snippets = ANYLOGIC_DIR / "java_snippets"
    if snippets.exists():
        for p in sorted(snippets.glob("*.java")):
            files[f"java_snippets/{p.name}"] = p.read_bytes()
    for name in ("BloodTypeLab.alp", "BloodTypeModel.java", "run_java.bat", "run_java.sh"):
        source = ANYLOGIC_DIR / name
        if source.exists():
            files[name] = source.read_bytes()
    return files


def export_anylogic_bundle(config: SimulationConfig, directory: Path | str) -> Path:
    out = Path(directory)
    out.mkdir(parents=True, exist_ok=True)
    for name, data in bundle_files(config).items():
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return out


def bundle_zip(config: SimulationConfig) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in bundle_files(config).items():
            zf.writestr(f"bloodtypelab_anylogic_bundle/{name}", data)
    return buf.getvalue()


# --------------------------------------------------------------------------------------
# Docking comparison
# --------------------------------------------------------------------------------------

@dataclass
class DockingReport:
    rows: pd.DataFrame
    verdict: str
    consistent: bool
    n_anylogic_replicates: int
    n_python_replicates: int
    notes: list[str] = field(default_factory=list)
    bands: dict[str, pd.DataFrame] = field(default_factory=dict)
    anylogic_shares: pd.DataFrame | None = None
    sufficient_evidence: bool = True


def read_anylogic_output(data: bytes | str | Path | pd.DataFrame) -> pd.DataFrame:
    if isinstance(data, pd.DataFrame):
        df = data.copy()
    elif isinstance(data, (bytes, bytearray)):
        df = pd.read_csv(io.BytesIO(data), sep=None, engine="python")
    else:
        df = pd.read_csv(data, sep=None, engine="python")
    df.columns = [str(c).strip() for c in df.columns]
    if df.empty or df.columns.duplicated().any():
        raise ValueError("AnyLogic output must have data rows and unique column names.")
    missing = [c for c in REQUIRED_OUTPUT if c not in df.columns]
    if missing:
        raise ValueError(f"AnyLogic output is missing column(s) {missing}. Expected {OUTPUT_COLUMNS} (+ optional 'replicate').")
    if "replicate" not in df.columns:
        df["replicate"] = 0
    numeric = REQUIRED_OUTPUT + ["replicate"] + (["rh_pos"] if "rh_pos" in df else [])
    for c in numeric:
        df[c] = pd.to_numeric(df[c], errors="raise")
        a = df[c].to_numpy(dtype=float)
        if not np.isfinite(a).all() or (a < 0).any() or (a != np.floor(a)).any():
            raise ValueError(f"AnyLogic column '{c}' must contain finite, non-negative integers.")
        if (a > np.iinfo(np.int64).max // 4).any():
            raise ValueError(f"AnyLogic column '{c}' contains an integer that is too large.")
        df[c] = df[c].astype(np.int64)
    if df.duplicated(["replicate", "step"]).any():
        raise ValueError("AnyLogic output has duplicate (replicate, step) rows.")
    pheno_sum = df[["n_A", "n_B", "n_AB", "n_O"]].sum(axis=1)
    if (pheno_sum != df["population"]).any():
        raise ValueError("In the AnyLogic output, n_A + n_B + n_AB + n_O must equal population on every row.")
    if "rh_pos" in df and (df["rh_pos"] > df["population"]).any():
        raise ValueError("AnyLogic rh_pos cannot exceed population.")
    n = df["population"].replace(0, np.nan).astype(float)
    for p in ABO_PHENOTYPES:
        df[f"share_{p}"] = df[f"n_{p}"] / n
    if "rh_pos" in df.columns:
        df["share_rh_pos"] = df["rh_pos"] / n
    return df.sort_values(["replicate", "step"]).reset_index(drop=True)


def compare_with_anylogic(anylogic: pd.DataFrame, python_runs: list[RunResult]) -> DockingReport:
    from .experiments import stack_metric, summarize_replicates
    if len(python_runs) < 2:
        raise ValueError("Docking needs at least two Python reference replicates.")
    al = read_anylogic_output(anylogic)
    cfg = python_runs[0].config
    expected = np.arange(cfg.horizon_steps + 1)
    reps = sorted(al["replicate"].unique())
    for rep, frame in al.groupby("replicate"):
        if not np.array_equal(frame["step"].to_numpy(), expected):
            raise ValueError(f"Replicate {rep} must contain every year 0..{cfg.horizon_steps}, exactly once.")
    identity = bundle_identity(cfg)
    if any(bundle_identity(r.config) != identity for r in python_runs):
        raise ValueError("Python reference runs do not share the same configuration and initial seed.")
    notes = []
    if "bundle_id" in al:
        if al["bundle_id"].isna().any() or not al["bundle_id"].eq(identity).all():
            raise ValueError("The output belongs to a different bundle. Load its exact configuration before comparing.")
    else:
        notes.append("Legacy CSV has no bundle_id: configuration identity cannot be verified.")
    if cfg.include_rh and "rh_pos" not in al:
        raise ValueError("This configuration includes RhD, so the output must include rh_pos.")
    initial_cols = REQUIRED_OUTPUT[1:] + (["rh_pos"] if cfg.include_rh else [])
    initial = python_runs[0].timeseries.iloc[0]
    for col in initial_cols:
        if not al.loc[al.step == 0, col].eq(initial[col]).all():
            raise ValueError(f"Initial {col} does not match the exported starting population.")
    metrics = [f"share_{p}" for p in ABO_PHENOTYPES]
    if cfg.include_rh:
        metrics.append("share_rh_pos")
    metrics.append("population")
    rows = []
    bands = {}
    # One family includes every metric/year mean test and every final-year KS test.
    family_size = len(metrics) * (len(expected) + 1)
    sufficient = len(reps) >= 5 and len(python_runs) >= 20 and "bundle_id" in al
    for m in metrics:
        band = summarize_replicates(python_runs, m)
        bands[m] = band
        py_matrix = stack_metric(python_runs, m)
        al_matrix = al.pivot(index="step", columns="replicate", values=m)
        p_values, t_values, inside_values = [], [], []
        for step in expected:
            a = al_matrix.loc[step].dropna().to_numpy(dtype=float)
            p = py_matrix.loc[step].dropna().to_numpy(dtype=float)
            # Extinction makes shares undefined. Compare extinction frequency separately below.
            extinct_a = al.loc[al.step == step, "population"].eq(0).to_numpy(dtype=float)
            extinct_p = np.array([r.timeseries.loc[r.timeseries.step == step, "population"].iloc[0] == 0 for r in python_runs], dtype=float)
            if m == "population" and (extinct_a.any() or extinct_p.any()):
                # Counts already test population collapse; also test the discrete extinction outcome.
                table = [[int(extinct_a.sum()), int(len(extinct_a)-extinct_a.sum())],
                         [int(extinct_p.sum()), int(len(extinct_p)-extinct_p.sum())]]
                p_values.append(float(stats.fisher_exact(table).pvalue))
            if not a.size and not p.size:
                continue
            if not a.size or not p.size:
                p_values.append(0.0)
                t_values.append(float("inf"))
                continue
            b = band.loc[band.step == step].iloc[0]
            inside_values.extend(((a >= b.p025) & (a <= b.p975)).tolist())
            if min(a.size, p.size) < 2:
                sufficient = False
                continue
            delta = a.mean() - p.mean()
            va, vp = a.var(ddof=1) / a.size, p.var(ddof=1) / p.size
            if va + vp < 1e-24:
                equal = bool(np.isclose(delta, 0, atol=1e-12, rtol=0))
                t_value, p_value = (0.0, 1.0) if equal else (float("inf"), 0.0)
            else:
                t_value = delta / np.sqrt(va + vp)
                dof = (va + vp) ** 2 / (va ** 2 / (a.size - 1) + vp ** 2 / (p.size - 1))
                p_value = float(2 * stats.t.sf(abs(t_value), dof))
            t_values.append(abs(t_value))
            p_values.append(p_value)
        py_final = py_matrix.loc[cfg.horizon_steps].dropna().to_numpy(dtype=float)
        al_final = al_matrix.loc[cfg.horizon_steps].dropna().to_numpy(dtype=float)
        ks_p = float(stats.ks_2samp(al_final, py_final).pvalue) if min(al_final.size, py_final.size) >= 5 else float("nan")
        if np.isfinite(ks_p):
            p_values.append(ks_p)
        # Include the possible per-year extinction tests in the conservative family bound.
        adjusted_p = min(1.0, min(p_values, default=1.0) * (family_size + len(expected)))
        scale = 1 if m == "population" else 100
        rows.append(
            {
                "metric": m.replace("share_", ""),
                "unit": "people" if m == "population" else "%",
                "steps_compared": len(expected),
                "inside_95_band": float(np.mean(inside_values)) if inside_values else float("nan"),
                "final_python_mean": py_final.mean() * scale if py_final.size else float("nan"),
                "final_anylogic_mean": al_final.mean() * scale if al_final.size else float("nan"),
                "max_abs_t": max(t_values, default=0.0),
                "min_adjusted_p": adjusted_p,
                "ks_p_value": ks_p,
                "passed": adjusted_p >= 0.05,
            }
        )
    df = pd.DataFrame(rows)
    consistent = bool(df["passed"].all()) and sufficient
    notes.append(
        "Welch mean tests over all years, final-year KS tests, and extinction checks use a joint Bonferroni correction. "
        "Both samples contribute their variance. Band coverage is descriptive. No detected difference is not proof of equivalence."
    )
    if not df["passed"].all():
        verdict = "Difference detected: check chronology, demographics, inheritance and shock rules."
    elif not sufficient:
        verdict = "Insufficient evidence: use at least 5 external and 20 Python runs, with a matching bundle_id."
    else:
        verdict = "No statistically detectable difference in the checked outputs; this does not prove equivalence."
    return DockingReport(df, verdict, consistent, len(reps), len(python_runs), notes, bands, al, sufficient)


def python_reference_runs(config: SimulationConfig, n_replicates: int = 20) -> list[RunResult]:
    """Python replicates that share the exported initial population (same seed) but vary dynamics."""
    return [simulate(replace(config, dynamics_seed=k)) for k in range(1, n_replicates + 1)]


def demo_anylogic_output(config: SimulationConfig, n_replicates: int = 5, seed_offset: int = 10_000) -> pd.DataFrame:
    """Generate a file in the AnyLogic output format FROM PYTHON (for demonstrating the docking UI only).

    Uses the exported initial population (same seed) with independent dynamics seeds, exactly as an
    AnyLogic model reading ``agents.csv`` would.
    """
    frames = []
    for k in range(n_replicates):
        r = simulate(replace(config, dynamics_seed=seed_offset + k))
        ts = r.timeseries[OUTPUT_COLUMNS].copy()
        ts.insert(0, "replicate", k)
        ts["bundle_id"] = bundle_identity(config)
        frames.append(ts)
    return pd.concat(frames, ignore_index=True)
