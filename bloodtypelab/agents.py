"""Agent schema and the structure-of-arrays population container.

Each living person is one row across a set of aligned NumPy arrays. This keeps the model
individual-based (every agent has its own sex, age and alleles and is subject to its own
random draws) while letting the engine apply rules to all agents at once.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

from .genetics import (
    ABO_ALLELES,
    ABO_GENOTYPES,
    ABO_PHENOTYPES,
    GENOTYPE_LUT,
    PHENOTYPE_LUT,
    RH_ALLELES,
    RH_GENOTYPE_LUT,
    RH_GENOTYPES,
    RH_PHENOTYPE_LUT,
    RH_PHENOTYPES,
)

Sex = Literal["F", "M"]
FEMALE, MALE = 0, 1


@dataclass(frozen=True)
class Agent:
    """Read-only view of one simulated person (synthetic, never a real individual)."""

    agent_id: int
    sex: Sex
    age: int
    abo_paternal: str
    abo_maternal: str
    rh_paternal: str
    rh_maternal: str
    birth_step: int
    rh_sensitized: bool = False

    @property
    def genotype(self) -> str:
        return ABO_GENOTYPES[GENOTYPE_LUT[ABO_ALLELES.index(self.abo_paternal), ABO_ALLELES.index(self.abo_maternal)]]

    @property
    def phenotype(self) -> str:
        return ABO_PHENOTYPES[PHENOTYPE_LUT[ABO_ALLELES.index(self.abo_paternal), ABO_ALLELES.index(self.abo_maternal)]]

    @property
    def rh_genotype(self) -> str:
        return RH_GENOTYPES[RH_GENOTYPE_LUT[RH_ALLELES.index(self.rh_paternal), RH_ALLELES.index(self.rh_maternal)]]

    @property
    def rh_phenotype(self) -> str:
        return RH_PHENOTYPES[RH_PHENOTYPE_LUT[RH_ALLELES.index(self.rh_paternal), RH_ALLELES.index(self.rh_maternal)]]


class IdAllocator:
    """Monotonic agent-ID source; IDs are never reused after death."""

    def __init__(self, start: int = 0) -> None:
        self._next = int(start)

    def take(self, n: int) -> np.ndarray:
        ids = np.arange(self._next, self._next + n, dtype=np.int64)
        self._next += n
        return ids

    @property
    def next_id(self) -> int:
        return self._next


class Population:
    """Aligned arrays describing the living population."""

    __slots__ = ("agent_id", "sex", "age", "abo1", "abo2", "rh1", "rh2", "birth_step", "sensitized")

    def __init__(
        self,
        agent_id: np.ndarray,
        sex: np.ndarray,
        age: np.ndarray,
        abo1: np.ndarray,
        abo2: np.ndarray,
        rh1: np.ndarray,
        rh2: np.ndarray,
        birth_step: np.ndarray,
        sensitized: np.ndarray | None = None,
    ) -> None:
        n = agent_id.shape[0]
        self.agent_id = agent_id.astype(np.int64, copy=False)
        self.sex = sex.astype(np.int8, copy=False)
        self.age = age.astype(np.int16, copy=False)
        self.abo1 = abo1.astype(np.int8, copy=False)  # paternal allele
        self.abo2 = abo2.astype(np.int8, copy=False)  # maternal allele
        self.rh1 = rh1.astype(np.int8, copy=False)
        self.rh2 = rh2.astype(np.int8, copy=False)
        self.birth_step = birth_step.astype(np.int32, copy=False)
        self.sensitized = (np.zeros(n, dtype=bool) if sensitized is None else sensitized.astype(bool, copy=False))
        for name in self.__slots__:
            if getattr(self, name).shape[0] != n:
                raise ValueError(f"Population array {name} has inconsistent length")

    # ------------------------------------------------------------------ basics
    @classmethod
    def empty(cls) -> "Population":
        z = np.zeros(0, dtype=np.int64)
        return cls(z, z, z, z, z, z, z, z, np.zeros(0, dtype=bool))

    def __len__(self) -> int:
        return int(self.agent_id.shape[0])

    @property
    def size(self) -> int:
        return len(self)

    def subset(self, mask_or_idx: np.ndarray) -> "Population":
        return Population(*(getattr(self, n)[mask_or_idx] for n in self.__slots__))

    def concat(self, other: "Population") -> "Population":
        if len(other) == 0:
            return self
        if len(self) == 0:
            return other
        return Population(*(np.concatenate([getattr(self, n), getattr(other, n)]) for n in self.__slots__))

    def copy(self) -> "Population":
        return Population(*(getattr(self, n).copy() for n in self.__slots__))

    # ------------------------------------------------------------------ derived
    @property
    def genotype_idx(self) -> np.ndarray:
        return GENOTYPE_LUT[self.abo1, self.abo2]

    @property
    def phenotype_idx(self) -> np.ndarray:
        return PHENOTYPE_LUT[self.abo1, self.abo2]

    @property
    def rh_genotype_idx(self) -> np.ndarray:
        return RH_GENOTYPE_LUT[self.rh1, self.rh2]

    @property
    def rh_phenotype_idx(self) -> np.ndarray:
        return RH_PHENOTYPE_LUT[self.rh1, self.rh2]

    def agent(self, i: int) -> Agent:
        return Agent(
            agent_id=int(self.agent_id[i]),
            sex="F" if self.sex[i] == FEMALE else "M",
            age=int(self.age[i]),
            abo_paternal=ABO_ALLELES[self.abo1[i]],
            abo_maternal=ABO_ALLELES[self.abo2[i]],
            rh_paternal=RH_ALLELES[self.rh1[i]],
            rh_maternal=RH_ALLELES[self.rh2[i]],
            birth_step=int(self.birth_step[i]),
            rh_sensitized=bool(self.sensitized[i]),
        )

    def to_frame(self, limit: int | None = None, include_rh: bool = True) -> pd.DataFrame:
        n = len(self) if limit is None else min(limit, len(self))
        sl = slice(0, n)
        g = self.genotype_idx[sl]
        p = self.phenotype_idx[sl]
        df = pd.DataFrame(
            {
                "agent_id": self.agent_id[sl],
                "sex": np.where(self.sex[sl] == FEMALE, "F", "M"),
                "age": self.age[sl].astype(int),
                "abo_paternal": np.array(ABO_ALLELES)[self.abo1[sl]],
                "abo_maternal": np.array(ABO_ALLELES)[self.abo2[sl]],
                "genotype": np.array(ABO_GENOTYPES)[g],
                "phenotype": np.array(ABO_PHENOTYPES)[p],
            }
        )
        if include_rh:
            df["rh_paternal"] = np.array(RH_ALLELES)[self.rh1[sl]]
            df["rh_maternal"] = np.array(RH_ALLELES)[self.rh2[sl]]
            df["rh_genotype"] = np.array(RH_GENOTYPES)[self.rh_genotype_idx[sl]]
            df["rh"] = np.array(RH_PHENOTYPES)[self.rh_phenotype_idx[sl]]
            df["blood_type"] = df["phenotype"] + df["rh"].str[-1]
        df["birth_step"] = self.birth_step[sl].astype(int)
        return df

    def check_integrity(self) -> list[str]:
        """Return a list of problems (empty if valid)."""
        problems: list[str] = []
        n = len(self)
        if n and np.unique(self.agent_id).shape[0] != n:
            problems.append("duplicate agent IDs")
        if n and (self.abo1.min() < 0 or self.abo1.max() > 2 or self.abo2.min() < 0 or self.abo2.max() > 2):
            problems.append("invalid ABO allele code")
        if n and (self.rh1.min() < 0 or self.rh1.max() > 1 or self.rh2.min() < 0 or self.rh2.max() > 1):
            problems.append("invalid RhD allele code")
        if n and self.age.min() < 0:
            problems.append("negative age")
        if n and not np.isin(self.sex, (FEMALE, MALE)).all():
            problems.append("invalid sex code")
        return problems
