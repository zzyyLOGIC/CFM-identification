"""Small, auditable exact-arithmetic boundary. No optimizer is imported here."""
from __future__ import annotations
import math
from fractions import Fraction

MAX_RATIONAL_CHARS = 4096

def fraction(value: object) -> Fraction:
    """Parse a finite JSON number or rational string without tolerance rounding."""
    if isinstance(value, bool):
        raise ValueError("Boolean is not a probability or a rational witness")
    if isinstance(value, Fraction):
        return value
    text = str(value)
    if len(text) > MAX_RATIONAL_CHARS:
        raise ValueError("rational representation exceeds the resource limit")
    try:
        result = Fraction(text)
    except (ValueError, ZeroDivisionError, OverflowError) as exc:
        raise ValueError("expected a finite decimal number or a rational n/d string") from exc
    if result.numerator.bit_length() > 16384 or result.denominator.bit_length() > 16384:
        raise ValueError("rational precision exceeds the resource limit")
    return result

def display(value: Fraction) -> float:
    ans = float(value)
    if not math.isfinite(ans):
        raise ValueError("rational value has no finite float display")
    return ans

def dot(a, b):
    if len(a) != len(b):
        raise ValueError("vector dimensions do not match")
    return sum((x*y for x,y in zip(a,b)), Fraction(0))

def matvec(A, x):
    return tuple(dot(row,x) for row in A)

def transpose(A):
    return tuple(tuple(col) for col in zip(*A))
