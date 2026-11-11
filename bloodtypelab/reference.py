"""Read-only, versioned reference datasets and hidden-genotype inference."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from .genetics import ABO_GENOTYPES, ABO_PHENOTYPES, RH_GENOTYPES, RH_PHENOTYPES, hwe_phenotype_frequencies

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "references"

REGISTRY: dict[str, dict[str, str]] = {
    "austria_gesundheitsportal_2022": {
        "file": "austria_abo_rh.csv",
        "kind": "observed",
        "title": "Austria - Gesundheitsportal (2022)",
        "badge": "Observed reference (secondary source, pending team verification)",
    },
    "synthetic_demo": {
        "file": "synthetic_demo.csv",
        "kind": "synthetic",
        "title": "Synthetic demo (NOT Austria)",
        "badge": "Synthetic, illustrative - not empirical",
    },
}

TOLERANCE = 0.005


class ReferenceError_(ValueError):
    pass


@dataclass(frozen=True)
class ReferenceData:
    reference_id: str
    title: str
    kind: str
    badge: str
    abo: dict[str, float]
    rh: dict[str, float]
    source_label: str
    source_url: str
    source_updated: str
    accessed: str
    population_covered: str
    notes: tuple[str, ...]
    file_sha256: str
    raw_abo_sum: float = 1.0
    raw_rh_sum: float = 1.0

    def metadata(self) -> dict:
        return {
            "reference_id": self.reference_id,
            "title": self.title,
            "kind": self.kind,
            "source_label": self.source_label,
            "source_url": self.source_url,
            "source_updated": self.source_updated,
            "accessed": self.accessed,
            "population_covered": self.population_covered,
            "notes": list(self.notes),
            "file_sha256": self.file_sha256,
            "abo": self.abo,
            "rh": self.rh,
        }

    def combined_shares(self) -> dict[str, float]:
        """ABO x Rh shares assuming independence of the two loci."""
        return {f"{a}{r[-1]}": self.abo[a] * self.rh[r] for a in ABO_PHENOTYPES for r in RH_PHENOTYPES}


def available_references() -> dict[str, dict[str, str]]:
    return dict(REGISTRY)


def _validate_shares(name: str, shares: dict[str, float], keys: tuple[str, ...]) -> float:
    if set(shares) != set(keys):
        raise ReferenceError_(f"{name} reference must contain exactly {list(keys)}, got {sorted(shares)}")
    vals = np.array([shares[k] for k in keys], dtype=float)
    if np.any(~np.isfinite(vals)) or np.any(vals < 0) or np.any(vals > 1):
        raise ReferenceError_(f"{name} shares must be finite and within [0, 1].")
    s = float(vals.sum())
    if abs(s - 1.0) > TOLERANCE:
        raise ReferenceError_(f"{name} shares sum to {s:.4f}, expected 1 +/- {TOLERANCE}.")
    return s


def reference_from_frame(df: pd.DataFrame, reference_id: str, title: str, kind: str, badge: str, sha: str) -> ReferenceData:
    required = {"system", "category", "share"}
    if not required <= set(df.columns):
        raise ReferenceError_(f"Reference file needs columns {sorted(required)}.")
    abo = {r.category: float(r.share) for r in df[df.system == "ABO"].itertuples()}
    rh = {r.category: float(r.share) for r in df[df.system == "RH"].itertuples()}
    s_abo = _validate_shares("ABO", abo, ABO_PHENOTYPES)
    s_rh = _validate_shares("Rh", rh, RH_PHENOTYPES)
    # Normalise tiny rounding residue but remember the raw sum for the manifest.
    abo = {k: v / s_abo for k, v in abo.items()}
    rh = {k: v / s_rh for k, v in rh.items()}
    first = df.iloc[0]

    def _s(col: str) -> str:
        v = first.get(col, "")
        return "" if pd.isna(v) else str(v)

    notes = tuple(sorted({str(n) for n in df.get("notes", pd.Series(dtype=str)).dropna()}))
    return ReferenceData(
        reference_id=reference_id,
        title=title,
        kind=kind,
        badge=badge,
        abo=abo,
        rh=rh,
        source_label=_s("source_label"),
        source_url=_s("source_url"),
        source_updated=_s("source_updated"),
        accessed=_s("accessed"),
        population_covered=_s("population_covered"),
        notes=notes,
        file_sha256=sha,
        raw_abo_sum=s_abo,
        raw_rh_sum=s_rh,
    )


@lru_cache(maxsize=16)
def load_reference(reference_id: str) -> ReferenceData:
    if reference_id not in REGISTRY:
        raise ReferenceError_(f"Unknown reference_id {reference_id!r}. Available: {sorted(REGISTRY)}")
    meta = REGISTRY[reference_id]
    path = DATA_DIR / meta["file"]
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    df = pd.read_csv(path)
    return reference_from_frame(df, reference_id, meta["title"], meta["kind"], meta["badge"], sha)


def custom_reference(abo: dict[str, float], rh: dict[str, float], title: str = "Custom (hypothetical)") -> ReferenceData:
    _validate_shares("ABO", abo, ABO_PHENOTYPES)
    _validate_shares("Rh", rh, RH_PHENOTYPES)
    sa, sr = sum(abo.values()), sum(rh.values())
    return ReferenceData(
        reference_id="custom",
        title=title,
        kind="hypothetical",
        badge="Hypothetical, user-defined",
        abo={k: v / sa for k, v in abo.items()},
        rh={k: v / sr for k, v in rh.items()},
        source_label="User input",
        source_url="",
        source_updated="",
        accessed="",
        population_covered="none",
        notes=("User-defined hypothetical distribution",),
        file_sha256="",
    )


# --------------------------------------------------------------------------------------
# Genotype inference
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class InferenceResult:
    method: str
    allele_freqs: dict[str, float]
    genotype_freqs: dict[str, float]
    implied_phenotypes: dict[str, float]
    residuals: dict[str, float]  # implied - target (fraction)
    rh_allele_freqs: dict[str, float]
    rh_genotype_freqs: dict[str, float]
    iterations: int = 0
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def max_abs_residual(self) -> float:
        return max(abs(v) for v in self.residuals.values())


def _em_abo(f: dict[str, float], tol: float = 1e-12, max_iter: int = 10_000) -> tuple[float, float, float, int]:
    """Gene-counting EM for ABO allele frequencies under Hardy-Weinberg (Ceppellini et al. 1955)."""
    fa, fb, fab, fo = f["A"], f["B"], f["AB"], f["O"]
    p, q, r = 1 / 3, 1 / 3, 1 / 3
    for it in range(1, max_iter + 1):
        den_a = p * p + 2 * p * r
        den_b = q * q + 2 * q * r
        aa = fa * (p * p / den_a) if den_a > 0 else 0.0
        ao = fa - aa
        bb = fb * (q * q / den_b) if den_b > 0 else 0.0
        bo = fb - bb
        p_new = (2 * aa + ao + fab) / 2
        q_new = (2 * bb + bo + fab) / 2
        r_new = (ao + bo + 2 * fo) / 2
        if max(abs(p_new - p), abs(q_new - q), abs(r_new - r)) < tol:
            return p_new, q_new, r_new, it
        p, q, r = p_new, q_new, r_new
    return p, q, r, max_iter


def _bernstein(f: dict[str, float]) -> tuple[float, float, float, float]:
    r = np.sqrt(f["O"])
    p = 1 - np.sqrt(f["B"] + f["O"])
    q = 1 - np.sqrt(f["A"] + f["O"])
    d = 1 - p - q - r
    # Bernstein's correction
    p2, q2, r2 = p * (1 + d / 2), q * (1 + d / 2), (r + d / 2) * (1 + d / 2)
    s = p2 + q2 + r2
    return float(p2 / s), float(q2 / s), float(r2 / s), float(d)


def infer_genotype_frequencies(
    reference: ReferenceData,
    method: str = "hwe_em",
    aa_fraction: float = 0.3,
    bb_fraction: float = 0.1,
) -> InferenceResult:
    """Infer hidden ABO genotype frequencies (and RhD) from phenotype shares."""
    f = reference.abo
    notes: list[str] = []
    iterations = 0
    if method == "hwe_em":
        p, q, r, iterations = _em_abo(f)
        g = {"AA": p * p, "AO": 2 * p * r, "BB": q * q, "BO": 2 * q * r, "AB": 2 * p * q, "OO": r * r}
        notes.append("Maximum-likelihood allele frequencies under Hardy-Weinberg equilibrium (gene-counting EM).")
    elif method == "hwe_bernstein":
        p, q, r, d = _bernstein(f)
        g = {"AA": p * p, "AO": 2 * p * r, "BB": q * q, "BO": 2 * q * r, "AB": 2 * p * q, "OO": r * r}
        notes.append(f"Bernstein closed-form estimator with correction; Bernstein D = {d:+.5f}.")
    elif method == "explicit_split":
        if not (0 <= aa_fraction <= 1 and 0 <= bb_fraction <= 1):
            raise ValueError("aa_fraction and bb_fraction must be in [0, 1].")
        g = {
            "AA": f["A"] * aa_fraction,
            "AO": f["A"] * (1 - aa_fraction),
            "BB": f["B"] * bb_fraction,
            "BO": f["B"] * (1 - bb_fraction),
            "AB": f["AB"],
            "OO": f["O"],
        }
        p = g["AA"] + 0.5 * (g["AO"] + g["AB"])
        q = g["BB"] + 0.5 * (g["BO"] + g["AB"])
        r = g["OO"] + 0.5 * (g["AO"] + g["BO"])
        notes.append(
            f"Explicit split: {aa_fraction:.0%} of phenotype A are AA, {bb_fraction:.0%} of phenotype B are BB. "
            "Reproduces phenotype targets exactly; not an equilibrium assumption."
        )
    else:
        raise ValueError(f"Unknown inference method {method!r}")

    s = sum(g.values())
    g = {k: g[k] / s for k in ABO_GENOTYPES}
    implied = {
        "A": g["AA"] + g["AO"],
        "B": g["BB"] + g["BO"],
        "AB": g["AB"],
        "O": g["OO"],
    }
    if method != "explicit_split":
        implied = hwe_phenotype_frequencies(p, q, r)
    residuals = {k: implied[k] - f[k] for k in ABO_PHENOTYPES}

    d_freq = float(np.sqrt(reference.rh["Rh-"]))
    rh_alleles = {"D": 1 - d_freq, "d": d_freq}
    rh_g = {"DD": (1 - d_freq) ** 2, "Dd": 2 * d_freq * (1 - d_freq), "dd": d_freq**2}
    notes.append("RhD: d = sqrt(Rh- share) under Hardy-Weinberg; reproduces the Rh+/Rh- split exactly.")
    return InferenceResult(
        method=method,
        allele_freqs={"A": float(p), "B": float(q), "O": float(r)},
        genotype_freqs={k: float(v) for k, v in g.items()},
        implied_phenotypes={k: float(v) for k, v in implied.items()},
        residuals={k: float(v) for k, v in residuals.items()},
        rh_allele_freqs=rh_alleles,
        rh_genotype_freqs={k: float(rh_g[k]) for k in RH_GENOTYPES},
        iterations=iterations,
        notes=tuple(notes),
    )
