"""Cryptographic utilities for the generalized bounded solver.

Replaces the external cfm_id_bridge.scientific_binding.sha()
with a local deterministic implementation using hashlib.sha256.
"""
import hashlib
import json
from fractions import Fraction


def _sha(obj) -> str:
    """Deterministic SHA-256 hex digest of an arbitrary Python object.

    Uses JSON serialization with sorted keys for deterministic output.
    Handles Fraction objects via a custom encoder.
    """
    class FractionEncoder(json.JSONEncoder):
        def default(self, o):
            if isinstance(o, Fraction):
                return {'__Fraction__': True, 'n': o.numerator, 'd': o.denominator}
            return super().default(o)

    raw = json.dumps(obj, cls=FractionEncoder, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()