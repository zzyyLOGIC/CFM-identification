"""Exact observed-data contract for the binary instrumental-variable model."""
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from itertools import product
from math import isfinite

Cell = tuple[int, int, int]
CELLS = tuple(product(range(2), repeat=3))


class IVInputError(ValueError):
    def __init__(self, code: str, detail: str = ""):
        self.code, self.detail = code, detail
        super().__init__(code if not detail else f"{code}: {detail}")


def rational(value):
    """A float describes its displayed decimal. Preserve exact decimal and fraction inputs."""
    if isinstance(value, bool):
        raise IVInputError("NUMERIC_PROBABILITY_REQUIRED")
    if isinstance(value, Fraction):
        return value
    try:
        if isinstance(value,str) and "/" in value:
            if len(value)>4096:
                raise IVInputError("IV_PRECISION_LIMIT")
            return Fraction(value)
        dec=Decimal(str(value))
    except (InvalidOperation, ValueError, ZeroDivisionError, TypeError) as exc:
        raise IVInputError("NUMERIC_PROBABILITY_REQUIRED") from exc
    if not dec.is_finite():
        raise IVInputError("PROBABILITY_OUT_OF_RANGE")
    if abs(dec.as_tuple().exponent)>4096 or len(dec.as_tuple().digits)>4096:
        raise IVInputError("IV_PRECISION_LIMIT")
    return Fraction(dec)


def validate_observed(observed: Mapping, tol: float = 1e-8) -> dict[Cell, Fraction]:
    """Read the eight exact population probabilities P(D,Y|Z) without rounding or clipping."""
    if not isinstance(observed, Mapping):
        raise IVInputError("OBSERVED_LAW_MAPPING_REQUIRED")
    if isinstance(tol,bool) or not isfinite(tol) or not 0<tol<=1e-6:
        raise IVInputError("INVALID_TOLERANCE")
    if set(observed)!=set(CELLS):
        raise IVInputError("INCOMPLETE_OR_EXTRA_OBSERVED_CELLS")
    law={}
    for key,value in observed.items():
        if type(key) is not tuple or any(type(k) is not int for k in key):
            raise IVInputError("BINARY_CELL_COORDINATES_REQUIRED")
        x=rational(value)
        if not 0<=x<=1:
            raise IVInputError("PROBABILITY_OUT_OF_RANGE", repr(key))
        law[key]=x
    for z in (0,1):
        if sum(law[z,d,y] for d,y in product(range(2), repeat=2))!=1:
            raise IVInputError("CONDITIONAL_LAW_NOT_NORMALIZED",f"Z={z}")
    return law
