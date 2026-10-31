"""Interface every discharge source implements. Models only ever see the common schema."""
from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class DischargeSource(ABC):
    #: "simulation" or "observation": copied into every row so the two can never be confused
    kind: str
    name: str

    @abstractmethod
    def load(self) -> pd.DataFrame:
        """Return daily discharge in the common schema (see mekong_flood.schema)."""
