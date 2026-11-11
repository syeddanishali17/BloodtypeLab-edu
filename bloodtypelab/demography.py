"""Age-dependent mortality and fertility schedules (annual probabilities).

The default profile is ILLUSTRATIVE and UNCALIBRATED. It produces a life expectancy of
roughly 80 years and replacement-level fertility so that the neutral baseline is
demographically stable; it is not fitted to Statistik Austria data.
"""
from __future__ import annotations

import numpy as np

from .config import DemographyConfig


def mortality_schedule(cfg: DemographyConfig) -> np.ndarray:
    """Annual death probability q(x) for ages 0..max_age (q[max_age] = 1)."""
    ages = np.arange(cfg.max_age + 1, dtype=float)
    hazard = cfg.makeham_a + cfg.gompertz_b * np.exp(cfg.gompertz_c * ages)
    q = 1.0 - np.exp(-hazard)
    q[0] = cfg.infant_mortality
    q[cfg.max_age] = 1.0
    return np.clip(q, 0.0, 1.0)


def survivorship(cfg: DemographyConfig) -> np.ndarray:
    """l(x): probability of being alive at exact age x (l(0) = 1), x = 0..max_age."""
    q = mortality_schedule(cfg)
    lx = np.ones(cfg.max_age + 1)
    lx[1:] = np.cumprod(1.0 - q[:-1])
    return lx


def life_expectancy(cfg: DemographyConfig) -> float:
    """Period life expectancy at birth (deaths assumed mid-year)."""
    lx = survivorship(cfg)
    lx_next = np.append(lx[1:], 0.0)
    return float(((lx + lx_next) / 2).sum())


def stationary_age_distribution(cfg: DemographyConfig) -> np.ndarray:
    """Age weights of a stationary population: proportional to l(x), ages 0..max_age-1."""
    lx = survivorship(cfg)[: cfg.max_age]
    return lx / lx.sum()


def fertility_schedule(cfg: DemographyConfig) -> np.ndarray:
    """Annual probability of giving birth f(x) for women, ages 0..max_age.

    Gaussian-shaped over the reproductive window and scaled so that sum f(x) = TFR.
    """
    ages = np.arange(cfg.max_age + 1, dtype=float)
    w = np.exp(-0.5 * ((ages - cfg.fertility_mean_age) / cfg.fertility_sd) ** 2)
    window = (ages >= cfg.female_min_age) & (ages <= cfg.female_max_age)
    w = np.where(window, w, 0.0)
    total = w.sum()
    if total <= 0 or cfg.tfr == 0:
        return np.zeros_like(ages)
    f = w / total * cfg.tfr
    if f.max() > 1.0:
        raise ValueError("Fertility schedule exceeds one birth per woman per year; lower TFR or widen the schedule.")
    return f


def net_reproduction_rate(cfg: DemographyConfig) -> float:
    """R0 = sum l(x) f(x) * share_female: expected daughters per newborn girl."""
    return float((survivorship(cfg) * fertility_schedule(cfg)).sum() * cfg.sex_ratio_female)


def regulation_factor(cfg: DemographyConfig, population: int, capacity: int) -> float:
    """Density regulation of fertility: (K / N) ** strength (1 if disabled)."""
    if not cfg.regulation or population <= 0:
        return 1.0
    return float((capacity / population) ** cfg.regulation_strength)
