"""Fitness (selection) presets and per-agent fitness arrays.

All non-neutral values are HYPOTHETICAL sensitivity settings unless stated otherwise.
They exist to answer Task 2 ("find rules how the blood type influences fitness"), not to
claim that any blood group is superior.
"""
from __future__ import annotations

from dataclasses import replace

import numpy as np

from .config import SelectionConfig
from .genetics import ABO_PHENOTYPES, RH_PHENOTYPES


def _abo(**overrides: float) -> dict[str, float]:
    d = {p: 1.0 for p in ABO_PHENOTYPES}
    d.update(overrides)
    return d


PRESETS: dict[str, dict] = {
    "neutral": {
        "title": "Neutral (control)",
        "status": "control",
        "description": "No blood-type effect on survival or fertility. Any change is genetic drift, migration or shocks.",
        "config": SelectionConfig(),
    },
    "o_survival_advantage": {
        "title": "O survival advantage (RR 0.95)",
        "status": "hypothetical",
        "description": (
            "Annual hazard of phenotype O multiplied by 0.95. Loosely motivated by evidence that group O protects "
            "against severe falciparum malaria (Rowe et al. 2007) - not an Austrian effect; hypothetical magnitude."
        ),
        "config": SelectionConfig(preset="o_survival_advantage", status="hypothetical", survival_rr=_abo(O=0.95)),
    },
    "a_survival_disadvantage": {
        "title": "A survival disadvantage (RR 1.05)",
        "status": "hypothetical",
        "description": "Annual hazard of phenotype A multiplied by 1.05. Hypothetical sensitivity setting.",
        "config": SelectionConfig(preset="a_survival_disadvantage", status="hypothetical", survival_rr=_abo(A=1.05)),
    },
    "b_fecundity_advantage": {
        "title": "B fecundity advantage (w 1.05)",
        "status": "hypothetical",
        "description": "Phenotype B individuals have 5 % higher birth / partner-choice weight. Hypothetical.",
        "config": SelectionConfig(preset="b_fecundity_advantage", status="hypothetical", fecundity=_abo(B=1.05)),
    },
    "rh_hdn": {
        "title": "Rh incompatibility (HDN, pre-prophylaxis)",
        "status": "mechanism documented, magnitude hypothetical",
        "description": (
            "A sensitised Rh- mother loses an Rh+ pregnancy with probability 0.10 (haemolytic disease of the "
            "fetus and newborn, before anti-D prophylaxis). Selects against heterozygotes Dd; classic unstable "
            "polymorphism. Mechanism documented (Levine 1941), magnitude hypothetical."
        ),
        "config": SelectionConfig(preset="rh_hdn", status="mechanism documented, magnitude hypothetical", hdn_loss_probability=0.10),
    },
    "strong_o_advantage": {
        "title": "Strong O advantage (RR 0.80) - stress test",
        "status": "hypothetical",
        "description": "Deliberately exaggerated selection to show what a detectable selective sweep looks like.",
        "config": SelectionConfig(preset="strong_o_advantage", status="hypothetical", survival_rr=_abo(O=0.80)),
    },
}


def preset(name: str) -> SelectionConfig:
    if name not in PRESETS:
        raise KeyError(f"Unknown selection preset {name!r}")
    return PRESETS[name]["config"]


def custom_selection(
    survival_rr: dict[str, float],
    fecundity: dict[str, float],
    hdn_loss_probability: float = 0.0,
    rh_survival_rr: dict[str, float] | None = None,
    rh_fecundity: dict[str, float] | None = None,
) -> SelectionConfig:
    base = SelectionConfig(preset="custom", status="hypothetical")
    return replace(
        base,
        survival_rr={p: float(survival_rr.get(p, 1.0)) for p in ABO_PHENOTYPES},
        fecundity={p: float(fecundity.get(p, 1.0)) for p in ABO_PHENOTYPES},
        rh_survival_rr={p: float((rh_survival_rr or {}).get(p, 1.0)) for p in RH_PHENOTYPES},
        rh_fecundity={p: float((rh_fecundity or {}).get(p, 1.0)) for p in RH_PHENOTYPES},
        hdn_loss_probability=float(hdn_loss_probability),
    )


class FitnessArrays:
    """Lookup arrays indexed by phenotype codes."""

    def __init__(self, sel: SelectionConfig, include_rh: bool) -> None:
        self.surv_abo = np.array([sel.survival_rr[p] for p in ABO_PHENOTYPES], dtype=float)
        self.fec_abo = np.array([sel.fecundity[p] for p in ABO_PHENOTYPES], dtype=float)
        if include_rh:
            self.surv_rh = np.array([sel.rh_survival_rr[p] for p in RH_PHENOTYPES], dtype=float)
            self.fec_rh = np.array([sel.rh_fecundity[p] for p in RH_PHENOTYPES], dtype=float)
        else:
            self.surv_rh = np.ones(2)
            self.fec_rh = np.ones(2)
        self.survival_neutral = bool(np.all(self.surv_abo == 1) and np.all(self.surv_rh == 1))
        self.fecundity_neutral = bool(np.all(self.fec_abo == 1) and np.all(self.fec_rh == 1))

    def survival_rr(self, pheno_idx: np.ndarray, rh_idx: np.ndarray) -> np.ndarray:
        return self.surv_abo[pheno_idx] * self.surv_rh[rh_idx]

    def fecundity(self, pheno_idx: np.ndarray, rh_idx: np.ndarray) -> np.ndarray:
        return self.fec_abo[pheno_idx] * self.fec_rh[rh_idx]


def apply_relative_risk(q: np.ndarray, rr: np.ndarray) -> np.ndarray:
    """Proportional-hazards adjustment q' = 1 - (1 - q) ** rr, applied only where rr != 1.

    Keeps probabilities in [0, 1] for any rr >= 0 and leaves untouched agents bit-identical.
    """
    out = q.copy()
    mask = rr != 1.0
    if mask.any():
        out[mask] = 1.0 - np.power(1.0 - q[mask], rr[mask])
    return np.clip(out, 0.0, 1.0)
