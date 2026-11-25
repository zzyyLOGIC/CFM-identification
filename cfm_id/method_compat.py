"""Historical method identifiers at native proof / versioned API boundaries.

Current plans use descriptive identifiers. Never rewrite a certificate, its
hash, or an approved historical plan to migrate it. These functions translate
an identifier for lookup/comparison only; they grant no review or capability.
Unknown identifiers remain unknown and are rejected by the closed registry.
"""

_ALIASES = {
    'R1A_RANDOMIZED_ARM': 'network.randomized.local_mean',
    'R1A_COMPOSITION': 'network.randomized.local_contrast',
    'R1B_FULL_ASSIGNMENT': 'network.randomized.full_policy_mean',
    'R1B_FINITE_POLICY': 'network.randomized.finite_policy_mean',
    'R1B_ENDPOINT_DIFFERENCE': 'network.randomized.full_policy_contrast',
    'R2_MEAN_SIGNATURE': 'network.randomized.signature_policy_mean',
    'R2_ENDPOINT_DIFFERENCE': 'network.randomized.signature_policy_contrast',
    'R3_FULL_ASSIGNMENT': 'network.observational.full_policy_mean',
    'R3_MEAN_SIGNATURE': 'network.observational.signature_policy_mean',
    'R3_P_STANDARDIZED_EFFECTS': 'network.observational.observed_law_contrast',
    'R3_EXPOSURE_ADJUSTED_EFFECTS': 'network.observational.shared_stratum_contrast',
    'R3_NODEWISE_EXPOSURE_ADJUSTED_EFFECTS': 'network.observational.local_covariate_contrast',
}
_NATIVE = {current: old for old, current in _ALIASES.items()}
if len(_NATIVE) != len(_ALIASES):
    raise RuntimeError('AMBIGUOUS_METHOD_ALIAS')


def canonical_id(value):
    return _ALIASES.get(value, value)


def native_id(value):
    return _NATIVE.get(value, value)


def aliases():
    return dict(_ALIASES)


def native_network_routes():
    composed = {'network.randomized.full_policy_contrast', 'network.randomized.signature_policy_contrast'}
    return [old for old, current in _ALIASES.items() if current not in composed]


def legacy_attribute(name, namespace):
    """Old Python imports are supported here, not used by current consumers."""
    names = {'R1B': 'FULL_POLICY', 'R2': 'SIGNATURE_POLICY',
             'R1B_DIFFERENCE': 'FULL_POLICY_DIFFERENCE',
             'R2_DIFFERENCE': 'SIGNATURE_POLICY_DIFFERENCE',
             'R2_METHOD': 'SIGNATURE_METHOD',
             'R2_SCIENCE_DECISIONS': 'SIGNATURE_SCIENCE_DECISIONS',
             'R2_SIGNATURE_KINDS': 'SIGNATURE_KINDS'}
    if name not in names or names[name] not in namespace:
        raise AttributeError(name)
    return namespace[names[name]]
