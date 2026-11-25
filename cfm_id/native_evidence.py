"""Snapshot trusted in-memory native evidence; never reconstruct user classes."""
from dataclasses import fields, is_dataclass
from cfm_id_bridge.scientific_binding import canonical_data


def payload(value):
    import numpy as np
    import math
    # Preserve the existing TaskSpec evidence encoding, including finite floats.
    # This is not a coercion of causal weights or assignment probabilities.
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError('NONFINITE_NATIVE_SNAPSHOT')
        return value
    if isinstance(value, np.ndarray):
        return value.tolist()
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: payload(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, dict):
        return {k: payload(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [payload(v) for v in value]
    return canonical_data(value)
