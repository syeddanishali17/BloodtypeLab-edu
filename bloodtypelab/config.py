"""Typed, validated, immutable simulation configuration.

Every probability declares its time basis (per year or per transmission). Values in the
defaults are *illustrative* and are labelled as such in the assumptions register.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields, replace
from typing import Any, Literal

from .genetics import ABO_PHENOTYPES, RH_PHENOTYPES

SCHEMA_VERSION = "1.1"

ShockKind = Literal["immigration", "disease", "bottleneck"]
InitMethod = Literal["hwe_em", "hwe_bernstein", "explicit_split"]
Allocation = Literal["multinomial", "quota"]
DiseaseMode = Literal["relative_risk", "additional_probability"]

# Resource guard rails (agent-years). Benchmarked: ~2-4e7 agent-years/s on a laptop.
MAX_POPULATION = 200_000
MAX_HORIZON = 1_000
MAX_AGENT_YEARS_SINGLE = 2e8
MAX_AGENT_YEARS_BATCH = 5e8


class ConfigError(ValueError):
    """Raised when a configuration is invalid. Messages are meant for end users."""


def _prob(name: str, value: float) -> None:
    if not (0.0 <= float(value) <= 1.0):
        raise ConfigError(f"{name} must be a probability in [0, 1] (got {value}).")


@dataclass(frozen=True)
class DemographyConfig:
    """Illustrative, uncalibrated demographic profile (one-year time step)."""

    profile_id: str = "illustrative_uncalibrated"
    # Gompertz-Makeham annual hazard mu(x) = a + b * exp(c * x); q(x) = 1 - exp(-mu(x))
    makeham_a: float = 5e-4
    gompertz_b: float = 1.6e-5  # gives life expectancy ~80 years with the other defaults
    gompertz_c: float = 0.10
    infant_mortality: float = 0.004  # annual death probability at age 0
    max_age: int = 105  # death certain when reaching this age
    # Fertility: Gaussian-shaped age schedule scaled to a total fertility rate
    tfr: float = 2.1  # children per woman over the reproductive span
    fertility_mean_age: float = 30.0
    fertility_sd: float = 5.5
    female_min_age: int = 15
    female_max_age: int = 49
    male_min_age: int = 15
    male_max_age: int = 64
    # Density regulation of fertility: factor = (K / N) ** strength
    regulation: bool = True
    carrying_capacity: int | None = None  # None -> initial population size
    regulation_strength: float = 1.0
    sex_ratio_female: float = 0.5

    def validate(self) -> None:
        for n in ("makeham_a", "gompertz_b", "gompertz_c", "tfr", "fertility_sd", "regulation_strength"):
            if getattr(self, n) < 0:
                raise ConfigError(f"demography.{n} must be non-negative.")
        _prob("demography.infant_mortality", self.infant_mortality)
        _prob("demography.sex_ratio_female", self.sex_ratio_female)
        if self.tfr > 10:
            raise ConfigError("demography.tfr above 10 is not plausible for this model.")
        if not (1 <= self.max_age <= 130):
            raise ConfigError("demography.max_age must be between 1 and 130.")
        if not (0 <= self.female_min_age <= self.female_max_age < self.max_age):
            raise ConfigError("Female reproductive age window must satisfy 0 <= min <= max < max_age.")
        if not (0 <= self.male_min_age <= self.male_max_age < self.max_age):
            raise ConfigError("Male reproductive age window must satisfy 0 <= min <= max < max_age.")
        if self.fertility_sd <= 0:
            raise ConfigError("demography.fertility_sd must be positive.")
        if self.carrying_capacity is not None and self.carrying_capacity <= 0:
            raise ConfigError("demography.carrying_capacity must be positive.")


def _neutral_abo() -> dict[str, float]:
    return {p: 1.0 for p in ABO_PHENOTYPES}


def _neutral_rh() -> dict[str, float]:
    return {p: 1.0 for p in RH_PHENOTYPES}


@dataclass(frozen=True)
class SelectionConfig:
    """Phenotype-dependent fitness.

    * ``survival_rr``: relative risk applied to the annual hazard, q' = 1 - (1 - q) ** rr.
    * ``fecundity``: multiplicative weight on female birth probability and on the
      probability of being chosen as father.
    * ``hdn_loss_probability``: Rh maternal-fetal incompatibility; probability that an Rh+
      pregnancy of a *sensitised* Rh- mother is lost.
    """

    preset: str = "neutral"
    status: str = "control"
    survival_rr: dict[str, float] = field(default_factory=_neutral_abo)
    fecundity: dict[str, float] = field(default_factory=_neutral_abo)
    rh_survival_rr: dict[str, float] = field(default_factory=_neutral_rh)
    rh_fecundity: dict[str, float] = field(default_factory=_neutral_rh)
    hdn_loss_probability: float = 0.0

    def validate(self) -> None:
        for name, d, keys in (
            ("survival_rr", self.survival_rr, ABO_PHENOTYPES),
            ("fecundity", self.fecundity, ABO_PHENOTYPES),
            ("rh_survival_rr", self.rh_survival_rr, RH_PHENOTYPES),
            ("rh_fecundity", self.rh_fecundity, RH_PHENOTYPES),
        ):
            if set(d) != set(keys):
                raise ConfigError(f"selection.{name} must define exactly {list(keys)}.")
            for k, v in d.items():
                if not (0 <= float(v) <= 20):
                    raise ConfigError(f"selection.{name}[{k}] must be in [0, 20] (got {v}).")
        _prob("selection.hdn_loss_probability", self.hdn_loss_probability)

    @property
    def is_neutral(self) -> bool:
        return (
            all(v == 1.0 for v in self.survival_rr.values())
            and all(v == 1.0 for v in self.fecundity.values())
            and all(v == 1.0 for v in self.rh_survival_rr.values())
            and all(v == 1.0 for v in self.rh_fecundity.values())
            and self.hdn_loss_probability == 0.0
        )


@dataclass(frozen=True)
class MutationConfig:
    """Per-transmission ABO mutation; disabled (rate 0) by default."""

    rate: float = 0.0
    matrix: tuple[tuple[float, ...], ...] | None = None  # None -> uniform to the other alleles

    def validate(self) -> None:
        _prob("mutation.rate", self.rate)
        if self.matrix is not None:
            if len(self.matrix) != 3 or any(len(r) != 3 for r in self.matrix):
                raise ConfigError("mutation.matrix must be 3x3 (A, B, O).")
            for i, row in enumerate(self.matrix):
                if row[i] != 0 or abs(sum(row) - 1) > 1e-9 or min(row) < 0:
                    raise ConfigError("mutation.matrix rows must be non-negative, sum to 1, with zero diagonal.")


@dataclass(frozen=True)
class ShockConfig:
    """One external shock. Unused fields are ignored for other kinds."""

    kind: ShockKind
    start_step: int = 50
    duration_steps: int = 1
    label: str = ""
    # immigration
    count_per_step: int = 0
    source_allele_freqs: dict[str, float] = field(default_factory=lambda: {"A": 0.28, "B": 0.11, "O": 0.61})
    source_rh_neg_allele_freq: float = 0.44
    source_name: str = "hypothetical"
    age_min: int = 18
    age_max: int = 40
    # disease
    affected_phenotypes: tuple[str, ...] = ()
    affected_rh: tuple[str, ...] = ()  # empty = any Rh status
    mode: DiseaseMode = "relative_risk"
    relative_risk: float = 1.0
    additional_probability: float = 0.0
    # bottleneck
    fraction: float = 0.0

    def validate(self, horizon: int) -> None:
        if self.kind not in ("immigration", "disease", "bottleneck"):
            raise ConfigError(f"Unknown shock kind {self.kind!r}.")
        if not (1 <= self.start_step <= horizon):
            raise ConfigError(f"{self.kind} shock start_step must be within 1..{horizon} (got {self.start_step}).")
        if self.duration_steps < 1:
            raise ConfigError(f"{self.kind} shock duration must be at least 1 step.")
        if self.kind == "immigration":
            if self.count_per_step < 0 or self.count_per_step > MAX_POPULATION:
                raise ConfigError("Immigration count per step must be within 0..200000.")
            if set(self.source_allele_freqs) != {"A", "B", "O"}:
                raise ConfigError("Immigration source allele frequencies must define A, B and O.")
            if any(v < 0 for v in self.source_allele_freqs.values()):
                raise ConfigError("Immigration allele frequencies must be non-negative.")
            if abs(sum(self.source_allele_freqs.values()) - 1) > 1e-6:
                raise ConfigError("Immigration allele frequencies must sum to 1.")
            _prob("immigration.source_rh_neg_allele_freq", self.source_rh_neg_allele_freq)
            if not (0 <= self.age_min <= self.age_max <= 100):
                raise ConfigError("Immigrant age range must satisfy 0 <= min <= max <= 100.")
        elif self.kind == "disease":
            if not self.affected_phenotypes:
                raise ConfigError("Disease shock needs at least one affected ABO phenotype.")
            bad = set(self.affected_phenotypes) - set(ABO_PHENOTYPES)
            if bad:
                raise ConfigError(f"Unknown phenotype(s) {sorted(bad)} in disease shock.")
            bad_rh = set(self.affected_rh) - set(RH_PHENOTYPES)
            if bad_rh:
                raise ConfigError(f"Unknown Rh phenotype(s) {sorted(bad_rh)} in disease shock.")
            if self.mode not in ("relative_risk", "additional_probability"):
                raise ConfigError("Disease mode must be 'relative_risk' or 'additional_probability'.")
            if not (0 <= self.relative_risk <= 100):
                raise ConfigError("Disease relative risk must be in [0, 100].")
            _prob("disease.additional_probability", self.additional_probability)
        elif self.kind == "bottleneck":
            _prob("bottleneck.fraction", self.fraction)

    def active(self, step: int) -> bool:
        return self.start_step <= step < self.start_step + self.duration_steps

    def describe(self) -> str:
        if self.label:
            return self.label
        span = f"years {self.start_step}-{self.start_step + self.duration_steps - 1}"
        if self.kind == "immigration":
            return f"Immigration {self.count_per_step}/yr ({self.source_name}), {span}"
        if self.kind == "disease":
            eff = (
                f"RR {self.relative_risk:g}" if self.mode == "relative_risk" else f"+{self.additional_probability:.1%}/yr"
            )
            rh = f" {'/'.join(self.affected_rh)}" if self.affected_rh else ""
            return f"Disease on {'/'.join(self.affected_phenotypes)}{rh} ({eff}), {span}"
        return f"Bottleneck {self.fraction:.0%} mortality, {span}"


@dataclass(frozen=True)
class SimulationConfig:
    initial_population: int = 5000
    horizon_steps: int = 150
    seed: int = 20261111
    dynamics_seed: int | None = None  # optional: vary dynamics while keeping the initial population fixed
    reference_id: str = "austria_gesundheitsportal_2022"
    initialization_method: InitMethod = "hwe_em"
    allocation: Allocation = "multinomial"
    explicit_split_aa_fraction: float = 0.3  # share of phenotype A that is AA (explicit_split only)
    explicit_split_bb_fraction: float = 0.1  # share of phenotype B that is BB (explicit_split only)
    include_rh: bool = True
    scenario: str = "baseline"
    demography: DemographyConfig = field(default_factory=DemographyConfig)
    selection: SelectionConfig = field(default_factory=SelectionConfig)
    mutation: MutationConfig = field(default_factory=MutationConfig)
    shocks: tuple[ShockConfig, ...] = ()
    agent_snapshot_size: int = 200
    strict_invariants: bool = True
    time_unit: str = "year"
    schema_version: str = SCHEMA_VERSION

    # ------------------------------------------------------------------ validation
    def validate(self) -> "SimulationConfig":
        if not isinstance(self.initial_population, int) or not (2 <= self.initial_population <= MAX_POPULATION):
            raise ConfigError(f"Initial population must be an integer between 2 and {MAX_POPULATION:,}.")
        if not isinstance(self.horizon_steps, int) or not (1 <= self.horizon_steps <= MAX_HORIZON):
            raise ConfigError(f"Horizon must be between 1 and {MAX_HORIZON} years.")
        if not (0 <= int(self.seed) < 2**63):
            raise ConfigError("Seed must be a non-negative integer.")
        if self.dynamics_seed is not None and not (0 <= int(self.dynamics_seed) < 2**63):
            raise ConfigError("Dynamics seed must be a non-negative integer.")
        if self.initialization_method not in ("hwe_em", "hwe_bernstein", "explicit_split"):
            raise ConfigError(f"Unknown initialization method {self.initialization_method!r}.")
        if self.allocation not in ("multinomial", "quota"):
            raise ConfigError(f"Unknown allocation {self.allocation!r}.")
        _prob("explicit_split_aa_fraction", self.explicit_split_aa_fraction)
        _prob("explicit_split_bb_fraction", self.explicit_split_bb_fraction)
        if self.time_unit != "year":
            raise ConfigError("Only yearly time steps are supported (all rates are annual).")
        load = self.estimated_agent_years()
        if load > MAX_AGENT_YEARS_SINGLE:
            raise ConfigError(
                f"Requested run is too large (~{load:.2g} agent-years > {MAX_AGENT_YEARS_SINGLE:.0g}). "
                "Reduce population, horizon or immigration volume."
            )
        self.demography.validate()
        self.selection.validate()
        self.mutation.validate()
        for s in self.shocks:
            s.validate(self.horizon_steps)
        if self.selection.hdn_loss_probability > 0 and not self.include_rh:
            raise ConfigError("The Rh-HDN fitness mechanism requires the RhD module (include_rh=True).")
        if any(s.affected_rh for s in self.shocks if s.kind == "disease") and not self.include_rh:
            raise ConfigError("A disease shock restricted by Rh status requires include_rh=True.")
        return self

    def estimated_agent_years(self) -> float:
        extra = sum(s.count_per_step * s.duration_steps for s in self.shocks if s.kind == "immigration")
        return float(self.initial_population + extra) * self.horizon_steps

    @property
    def carrying_capacity(self) -> int:
        return self.demography.carrying_capacity or self.initial_population

    def with_(self, **changes: Any) -> "SimulationConfig":
        return replace(self, **changes)

    # ------------------------------------------------------------------ (de)serialisation
    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["shocks"] = [asdict(s) for s in self.shocks]
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SimulationConfig":
        data = dict(data)
        known = {f.name for f in fields(cls)}
        unknown = set(data) - known
        if unknown:
            raise ConfigError(f"Unknown configuration field(s): {sorted(unknown)}")
        if "demography" in data and isinstance(data["demography"], dict):
            data["demography"] = _build(DemographyConfig, data["demography"])
        if "selection" in data and isinstance(data["selection"], dict):
            data["selection"] = _build(SelectionConfig, data["selection"])
        if "mutation" in data and isinstance(data["mutation"], dict):
            m = dict(data["mutation"])
            if m.get("matrix") is not None:
                m["matrix"] = tuple(tuple(float(x) for x in row) for row in m["matrix"])
            data["mutation"] = _build(MutationConfig, m)
        if "shocks" in data:
            shocks = []
            for s in data["shocks"]:
                if isinstance(s, ShockConfig):
                    shocks.append(s)
                    continue
                s = dict(s)
                for key in ("affected_phenotypes", "affected_rh"):
                    if key in s:
                        s[key] = tuple(s[key])
                shocks.append(_build(ShockConfig, s))
            data["shocks"] = tuple(shocks)
        return cls(**data)

    @classmethod
    def from_json(cls, text: str) -> "SimulationConfig":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ConfigError(f"Configuration is not valid JSON: {exc}") from exc
        return cls.from_dict(data)


def _build(klass, data: dict[str, Any]):
    known = {f.name for f in fields(klass)}
    unknown = set(data) - known
    if unknown:
        raise ConfigError(f"Unknown {klass.__name__} field(s): {sorted(unknown)}")
    return klass(**data)
