"""Reverse a verified ordinary ATE, without recoding treatment or changing Core.

The native engine identifies E[Y(1)-Y(0)].  For an explicitly reviewed 0-1
question the answer is its negative; an interval [L,U] maps to [-U,-L].
This is an adapter derivation, not a new identification theorem/certificate.
Only the native ordinary-ATE program types below are accepted.  Report replay
reruns their verifier and reconstructs this derivation from the bound reading.
"""
from cfm_id_llm.compact_study import digest


def reverse_verified_ate(result, target):
    from pfn_pipeline._internal.identification.schemas import (
        DifferenceFunctional, ManskiBinaryATEBoundsProgram, OneArmATEBoundsProgram,
    )

    if result.verification_status != "VERIFIED" or target["direction"] != "0-1":
        raise ValueError("POPULATION_ATE_ORIENTATION_NOT_VERIFIED")
    program = result.identified_functional or result.bound_program
    original = program.to_text() if program is not None else str(result.identified_set)
    operation = dict(
        version="population-ate-negation/1", operation="NEGATE_VERIFIED_ATE",
        native_direction="1-0", requested_direction="0-1", treatment_recoded=False,
        target_sha256=digest(target), native_result_sha256=digest(result.model_dump(mode="json")),
        native_formula=original,
    )
    if isinstance(program, DifferenceFunctional) and result.status.value == "POINT":
        if (program.left.treatment, program.right.treatment, program.left.outcome,
                program.right.outcome, program.left.treatment_value, program.right.treatment_value) != (
                "T", "T", "Y", "Y", 1, 0):
            raise ValueError("POPULATION_ATE_UNEXPECTED_NATIVE_TARGET")
        reversed_program = DifferenceFunctional(left=program.right, right=program.left)
        formula = reversed_program.to_text()
        operation["derived_functional"] = reversed_program.model_dump(mode="json")
    elif isinstance(program, (ManskiBinaryATEBoundsProgram, OneArmATEBoundsProgram)) and result.status.value == "PARTIAL":
        if (program.treatment, program.outcome) != ("T", "Y"):
            raise ValueError("POPULATION_ATE_UNEXPECTED_NATIVE_TARGET")
        if isinstance(program, OneArmATEBoundsProgram):
            lower, upper = program.endpoint_expressions()
        else:
            # This native formatter uses ', ' only between interval endpoints;
            # probability arguments use ',' without a space, with fixed T/Y.
            # Read the native expressions instead of duplicating Manski's rule.
            if not (original.startswith("[") and original.endswith("]")):
                raise ValueError("POPULATION_ATE_NATIVE_INTERVAL_FORMAT")
            endpoints = original[1:-1].split(", ")
            if len(endpoints) != 2:
                raise ValueError("POPULATION_ATE_NATIVE_INTERVAL_FORMAT")
            lower, upper = endpoints

        def negative(expression):
            return {"-inf": "+inf", "+inf": "-inf"}.get(expression, f"-({expression})")

        low, high = negative(upper), negative(lower)
        left, right = ("(" if low == "-inf" else "["), (")" if high == "+inf" else "]")
        formula = f"{left}{low}, {high}{right}"
        operation["derived_interval"] = dict(lower=low, upper=high,
            lower_closed=left == "[", upper_closed=right == "]")
    elif (program is None and result.status.value == "NO_USEFUL_ID"
          and result.identified_set == dict(type="unbounded_real_line", lower="-inf", upper="+inf")):
        formula = "(-inf, +inf)"
        operation["derived_interval"] = dict(lower="-inf", upper="+inf", lower_closed=False, upper_closed=False)
    else:
        raise ValueError("POPULATION_ATE_ORIENTATION_PROGRAM_NOT_SUPPORTED")
    operation["derived_formula"] = formula
    return formula, operation
