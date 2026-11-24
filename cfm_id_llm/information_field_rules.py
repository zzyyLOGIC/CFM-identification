"""Existing information-field restrictions shared by parser, schema and hints.

Only syntax/field compatibility, never source entailment or mathematical scope.
No candidate mutation, invented values, or permission to promote sample data.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class InformationRule:
    field: str
    trigger: str
    required_field: str
    required_value: str
    error_code: str

    def violated(self, source):
        values = getattr(source, self.field)
        active = bool(values) if self.trigger == 'nonempty' else any(x.value is not None for x in values)
        return active and getattr(source, self.required_field) != self.required_value

    def schema(self):
        trigger = ({'minItems': 1} if self.trigger == 'nonempty' else
                   {'contains': {'properties': {'value': {'not': {'type': 'null'}}}, 'required': ['value']}})
        return {'if': {'properties': {self.field: trigger}, 'required': [self.field]},
                'then': {'properties': {self.required_field: {'const': self.required_value}},
                         'required': [self.required_field]}}

    def diagnostic(self, index):
        return dict(field_path=f'/information/{index}/{self.field}', error_code=self.error_code,
                    field_rule=dict(field=self.field, trigger=self.trigger,
                                    required_field=self.required_field, required_value=self.required_value))


RULES = (
    InformationRule('assignment_cells', 'nonempty', 'operator', 'ASSIGNMENT_NODE_MEANS', 'ASSIGNMENT_CELLS_WITH_OTHER_OPERATOR'),
    InformationRule('signature_cells', 'nonempty', 'operator', 'NODE_SIGNATURE_MEANS', 'SIGNATURE_CELLS_WITH_OTHER_OPERATOR'),
    InformationRule('signature_cells', 'nonnull_values', 'availability', 'EXACT_POPULATION_VALUE', 'EXACT_VALUE_WITH_NONEXACT_INFORMATION'),
)


def require(source, code):
    rule = next(r for r in RULES if r.error_code == code)
    if rule.violated(source):
        raise ValueError(code)


def require_assignment_scope(source, nodes):
    """Same assignment-cell ownership in fixed and finite-policy readers."""
    if source.operator == 'ASSIGNMENT_NODE_MEANS':
        if any(len(z) != len(nodes) or any(v not in (0, 1) for v in z)
               for z in source.assignment_cells):
            raise ValueError('INVALID_ASSIGNMENT_CELLS')
    require(source, 'ASSIGNMENT_CELLS_WITH_OTHER_OPERATOR')
    cells = [tuple(z) for z in source.assignment_cells]
    if len(set(cells)) != len(cells):
        raise ValueError('DUPLICATE_INFORMATION_CELL')


def diagnose(information):
    return [rule.diagnostic(i) for i, source in enumerate(information)
            for rule in RULES if rule.violated(source)][:50]
