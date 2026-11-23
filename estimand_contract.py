"""Identification handoff schema mirrored from autocfm.schemas."""
from __future__ import annotations

from fractions import Fraction
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ARM_ORDER = ((0, 0), (0, 1), (1, 0), (1, 1))


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, str_strip_whitespace=True)


class Estimand(Contract):
    version: Literal['autocfm-estimand-1'] = 'autocfm-estimand-1'
    kind: Literal['DIRECT_EFFECT', 'SPILLOVER_EFFECT', 'LOCAL_TOTAL_EFFECT']
    node_ids: list[str]
    population: list[str]
    first: tuple[int, int]
    second: tuple[int, int]
    operation: Literal['FIRST_MINUS_SECOND']
    remaining_assignment: Literal['ORIGINAL_DESIGN_CONDITIONAL']
    assignment: dict
    exposure: str
    treatment: str
    outcome: str
    context: str
    unit_weights: list[str]
    target_fingerprint: str = Field(pattern=r'^[a-f0-9]{64}$')

    @model_validator(mode='after')
    def coordinates(self):
        if (self.first not in ARM_ORDER or self.second not in ARM_ORDER or self.first == self.second
                or not self.population or len(set(self.population)) != len(self.population)
                or not set(self.population) <= set(self.node_ids) or len(set(self.node_ids)) != len(self.node_ids)):
            raise ValueError('INVALID_ESTIMAND_COORDINATES')
        a,s = self.first; b,r = self.second
        if ((self.kind=='DIRECT_EFFECT' and not(a!=b and s==r)) or
            (self.kind=='SPILLOVER_EFFECT' and not(a==b and s!=r)) or
            (self.kind=='LOCAL_TOTAL_EFFECT' and not(a!=b and s!=r))):
            raise ValueError('EFFECT_KIND_AND_COORDINATES_DIFFER')
        expected = [Fraction(1,len(self.population)) if node in self.population else Fraction(0) for node in self.node_ids]
        if [Fraction(w) for w in self.unit_weights] != expected:
            raise ValueError('ONLY_REVIEWED_EQUAL_MEAN_POPULATION_SUPPORTED')
        return self
