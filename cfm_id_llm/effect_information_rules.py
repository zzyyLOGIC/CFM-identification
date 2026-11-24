"""Public field combinations for local-effect information, not source truth.

The same rules feed the request schema, parser and bounded recheck diagnostics.
No candidate correction, population promotion, approval or mathematical routing.
"""
from dataclasses import dataclass

VERSION = 'effect-information-combinations-1'


@dataclass(frozen=True)
class Combination:
    field: str
    trigger: str
    required_field: str
    required_value: str
    error_code: str

    def violated(self, source):
        value = getattr(source, self.field)
        active = bool(value) if self.trigger == 'nonempty' else value == self.trigger
        return active and getattr(source, self.required_field) != self.required_value

    def schema(self):
        condition = {'minItems': 1} if self.trigger == 'nonempty' else {'const': self.trigger}
        return {'if': {'properties': {self.field: condition}, 'required': [self.field]},
                'then': {'properties': {self.required_field: {'const': self.required_value}},
                         'required': [self.required_field]}}

    def diagnostic(self, index):
        # Locate the pair, without deciding which supplied value misreads source.
        return dict(field_path=f'/information/{index}', error_code=self.error_code,
                    field_combination=dict(field=self.field, trigger=self.trigger,
                        required_field=self.required_field, required_value=self.required_value))


RULES = (
    Combination('operator', 'FINITE_SAMPLE', 'availability', 'FINITE_SAMPLE', 'SAMPLE_OPERATOR_REQUIRES_SAMPLE_AVAILABILITY'),
    Combination('availability', 'FINITE_SAMPLE', 'operator', 'FINITE_SAMPLE', 'SAMPLE_AVAILABILITY_REQUIRES_SAMPLE_OPERATOR'),
    Combination('arm_cells', 'nonempty', 'operator', 'NODE_ARM_MEANS', 'ARM_CELLS_REQUIRE_ARM_INFORMATION'),
)


def require(source):
    for rule in RULES:
        if rule.violated(source):
            raise ValueError(rule.error_code)


def require_scope(source, *, nodes, exposure, edges):
    """Shared source scope for single-arm and contrast readers.

    A full-law label cannot consume a stray arm table. Validate every supplied
    cell, including cells outside the requested target; never trim or repair it.
    """
    from .network_design_reading import validate_exposure_coordinate
    require(source)
    if not set(source.outcome_nodes) <= set(nodes) or len(set(source.outcome_nodes)) != len(source.outcome_nodes):
        raise ValueError('INVALID_A4_NODE_SCOPE')
    cells = [(v.node, v.own, v.exposure) for v in source.arm_cells]
    if (len(set(cells)) != len(cells)
            or any(n not in source.outcome_nodes or a not in (0, 1)
                   or (type(e) is int and e < 0) for n, a, e in cells)):
        raise ValueError('INVALID_A4_ARM_CELLS')
    for cell in source.arm_cells:
        validate_exposure_coordinate(exposure, cell.node, cell.exposure, edges)


def diagnose(information):
    return [rule.diagnostic(i) for i, source in enumerate(information)
            for rule in RULES if rule.violated(source)][:50]


def annotate(schema):
    schema['$defs']['EffectInformation'].setdefault('allOf', []).extend(r.schema() for r in RULES)
