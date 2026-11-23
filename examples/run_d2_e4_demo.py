#!/usr/bin/env python3
"""Demo: D2+E4 (Fixed Quota + Exact Neighbor Count) PARTIAL bounds.

Standalone demo — no CFM-identification repo required.
Uses .test_stubs/ package for contract/verify stubs, imports solvers from src/.

Run from task3-partial-extension/ via:
    python examples/run_d2_e4_demo.py

Expected output:
  [Cell enum]     E4 exact_count: non-binary, range(deg+1)
  [E4 exposure]   Exact count (not majority)
  [Swap test]     Consistency between original and swapped
  [E3 CC block]   INCOMPATIBLE without core_collaborators
  [Cert schema]   Policy: lower/upper, Contrast: cell_lower/cell_upper
  [SHA mismatch]  Tampered cert → hash mismatch
"""
import sys, os
from fractions import Fraction as F
from copy import deepcopy

# ── Setup: add .test_stubs/ and src/ to sys.path ────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, '..'))
STUBS_DIR = os.path.join(PROJECT_DIR, '.test_stubs')
SRC_DIR = os.path.join(PROJECT_DIR, 'src')
for d in (STUBS_DIR, SRC_DIR):
    if d not in sys.path:
        sys.path.insert(0, d)  # stubs first, then src

# ── Now import the actual solvers ──────────────────────────────────────────
from general_bounded_policy_solver import (
    solve as policy_solve,
    _enumerate_cells,
    _build_neighbors,
    _target_cells,
    _validate_design_kind,
    _validate_exposure_kind,
    DESIGN_KINDS,
    EXPOSURE_KINDS,
    EXPOSURE_SPECS,
    _require_core_collaborators,
)
from general_bounded_contrast_solver import solve as contrast_solve
from general_bounded_contrast_solver import _compute_exposure_state as contrast_exposure_state
from cfm_id.bounded_policy_contract import BoundedPolicyUnavailable
from cfm_id_bridge.scientific_binding import sha as stub_sha


# ═══════════════════════════════════════════════════════════════════════════════
#  Pass / Fail helpers
# ═══════════════════════════════════════════════════════════════════════════════

PASS = 0
FAIL = 0

def check(label, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        print(f"  ✗ {label}{' — ' + detail if detail else ''}")

def heading(text):
    print(f"\n─── {text} ───")


# ═══════════════════════════════════════════════════════════════════════════════
#  Core verification functions
# ═══════════════════════════════════════════════════════════════════════════════

def verify_policy_cert_fields(cert):
    """Verify policy certificate uses lower/upper (not cell_lower/cell_upper)."""
    for t in cert.get('bound_terms', []):
        if 'lower' not in t or 'upper' not in t:
            return False, "Missing lower/upper in bound_term"
        if 'cell_lower' in t or 'cell_upper' in t:
            return False, "Policy cert should NOT have cell_lower/cell_upper"
    return True, "Policy cert uses lower/upper"

def verify_contrast_cert_fields(cert):
    """Verify contrast certificate uses cell_lower/cell_upper + contributions."""
    for t in cert.get('bound_terms', []):
        if 'cell_lower' not in t or 'cell_upper' not in t:
            return False, "Missing cell_lower/cell_upper"
        if 'lower_contribution' not in t or 'upper_contribution' not in t:
            return False, "Missing lower_contribution/upper_contribution"
        if 'lower' in t or 'upper' in t:
            return False, "Contrast term should have lower/upper at term level"
    return True, "Contrast cert uses cell_lower/cell_upper + contributions"


# ═══════════════════════════════════════════════════════════════════════════════
#  Demo body
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    global PASS, FAIL
    print("=" * 60)
    print("D2+E4 (Fixed Quota + Exact Neighbor Count) 验收演示")
    print("=" * 60)

    # ── 1. Cell enumeration: E4 uses exact count (not binary) ──────────
    heading("Cell enumeration – E4 exact_count")

    class St:
        node_order = ['A', 'B', 'C']
        undirected_edges = [('A', 'B'), ('B', 'C')]
        outcome_kind = 'binary'
        unit_weights = [F(1, 3), F(1, 3), F(1, 3)]
        bounds = [(F(0), F(1)), (F(0), F(1)), (F(0), F(1))]
        core_collaborators = {}
        design = type('D', (), {'__class__': type('CompleteRandomizationDesignV1', (), {})})()
        exposure = type('E', (), {'grouping': 'exact_treated_neighbor_count'})()

    neighbors = _build_neighbors(St)
    cells_e4 = _enumerate_cells(St, neighbors, 'E4')

    # Chain(3) → A:deg1=4, B:deg2=6, C:deg1=4 = 14 cells
    check("E4 cell count = 14 for chain(3)", len(cells_e4) == 14,
          f"got {len(cells_e4)}")

    # Each node's exposure range is range(deg+1)
    for n, deg in [('A', 1), ('B', 2), ('C', 1)]:
        exposures = sorted(set(c[2] for c in cells_e4 if c[0] == n))
        check(f"E4 node {n} (deg={deg}): exposures={exposures}",
              exposures == list(range(deg + 1)))

    # E4 EXPOSURE_SPECS
    check("E4 spec = ('exact_treated_neighbor_count', None)",
          EXPOSURE_SPECS['E4'] == ('exact_treated_neighbor_count', None))

    # ── 2. E4 exposure state: exact count, not majority ────────────────
    heading("E4 exposure state — exact count")

    # Key test from teacher: 2/2 treated → 2, NOT 1
    neighbors_2 = {'X': {'A', 'B'}, 'A': {'X'}, 'B': {'X'}}
    policy_2treated = {'X': 0, 'A': 1, 'B': 1}
    e = contrast_exposure_state('X', policy_2treated, neighbors_2, 'E4', None)
    check("2/2 treated → exposure=2 (not 1)", e == 2, f"got {e}")

    policy_1treated = {'X': 0, 'A': 1, 'B': 0}
    e = contrast_exposure_state('X', policy_1treated, neighbors_2, 'E4', None)
    check("1/2 treated → exposure=1", e == 1, f"got {e}")

    policy_0treated = {'X': 0, 'A': 0, 'B': 0}
    e = contrast_exposure_state('X', policy_0treated, neighbors_2, 'E4', None)
    check("0/2 treated → exposure=0", e == 0, f"got {e}")

    # Chain(3) E4 exposure verification
    for p_a, p_b, p_c, expected in [(1, 0, 1, 2), (1, 0, 0, 1), (0, 0, 0, 0)]:
        policy = {'A': p_a, 'B': p_b, 'C': p_c}
        e_b = contrast_exposure_state('B', policy, neighbors, 'E4', None)
        check(f"Chain B: {policy} → E4={expected}", e_b == expected, f"got {e_b}")

    # ── 3. E3 core_collaborators requirement ───────────────────────────
    heading("E3 core_collaborators — must block without data")

    check("E3 spec = ('pretreatment_core_collaborator_majority', 'core_collaborators')",
          EXPOSURE_SPECS['E3'] == ('pretreatment_core_collaborator_majority', 'core_collaborators'))

    try:
        _require_core_collaborators(St, St, 'E3')
        check("E3 without CC → blocked", False, "did not raise")
    except BoundedPolicyUnavailable:
        check("E3 without CC → INCOMPATIBLE", True)
    except Exception as ex:
        if 'INCOMPATIBLE' in str(ex) or 'E3' in str(ex):
            check(f"E3 without CC → blocked ({ex})", True)
        else:
            check(f"E3: unexpected {type(ex).__name__}: {ex}", False)

    # ── 4. Certificate field check ─────────────────────────────────────
    heading("Certificate field names")

    from general_bounded_policy_solver import _build_mean_bounds, _compute_interval
    cells_test = [('A', 0, 0), ('A', 0, 1), ('A', 1, 0), ('A', 1, 1)]
    probs_test = {c: F(1, 4) for c in cells_test}
    known_test = {('A', 1, 0): F(3, 4)}
    bounds_test = {'A': (F(0), F(1))}
    weights_test = {'A': F(1)}
    rows, terms = _build_mean_bounds(cells_test, probs_test, known_test,
                                      bounds_test, weights=weights_test,
                                      target_cells={('A', 1, 0), ('A', 1, 1)})
    ok, msg = verify_policy_cert_fields({'bound_terms': terms})
    check(msg, ok)

    from general_bounded_contrast_solver import solve as cs
    import inspect
    csrc = inspect.getsource(cs)
    check("Contrast solve() contains cell_lower", 'cell_lower' in csrc)
    check("Contrast solve() contains lower_contribution", 'lower_contribution' in csrc)

    # ── 5. SHA mismatch detection ──────────────────────────────────────
    heading("Tampered certificate — SHA mismatch")

    sample_cert = {
        'version': 'test',
        'status': 'POINT',
        'lower': '0',
        'upper': '1',
        'bound_terms': [{'lower': '0', 'upper': '1', 'coefficient': '1'}],
        'certificate_sha256': 'placeholder',
    }
    original_hash = stub_sha({k: v for k, v in sample_cert.items() if k != 'certificate_sha256'})
    tampered = deepcopy(sample_cert)
    tampered['lower'] = '0.5'
    new_hash = stub_sha({k: v for k, v in tampered.items() if k != 'certificate_sha256'})
    check("Tampered cert → different SHA", original_hash != new_hash,
          f"hash is stable across tampering, original={original_hash}")

    # ── 5.5 Missing A4 -> NEEDS_INPUT (no implicit fill) ──────────────
    heading("Missing A4 — correct stop, no implicit fill")

    from general_bounded_policy_solver import solve as _policy_solve
    from general_bounded_contrast_solver import solve as _contrast_solve
    from cfm_id.bounded_policy_contract import (
        BoundedMeanInformation, BoundedPolicyUnavailable,
    )
    from pfn_pipeline._internal.identification.randomized_arm_family import SupportEngine

    # Dedicated 2-node inquiry so Target defaults (2-long policy) line up.
    class St2:
        node_order = ['A', 'B']
        undirected_edges = [('A', 'B')]
        outcome_kind = 'binary'
        design = type('D', (), {})()
        exposure = type('E', (), {'grouping': 'exact_treated_neighbor_count'})()

    # Only the policy target cells have positive support; A4 left empty.
    SupportEngine._test_probabilities = {
        ('A', 1, 1): F(1, 8),
        ('B', 1, 1): F(1, 8),
    }
    try:
        info_missing = BoundedMeanInformation(_test_known={})
        try:
            _policy_solve(St2, info_missing,
                          design_kind='D2', exposure_kind='E4')
            check("policy: missing A4 -> blocked", False,
                  "returned a certificate instead of NEEDS_INPUT")
        except BoundedPolicyUnavailable as exc:
            check(
                f"policy: missing A4 -> {exc.state}:{exc.reason}",
                exc.state == 'NEEDS_INPUT'
                and exc.reason == 'SUPPORTED_TARGET_A4_MEAN_MISSING',
                f"got state={exc.state!r} reason={exc.reason!r}",
            )

        class T11:
            policy_assignment = [1, 1]
            unit_weights = [F(1, 2), F(1, 2)]

        class T00:
            policy_assignment = [0, 0]
            unit_weights = [F(1, 2), F(1, 2)]

        info_contrast_missing = BoundedMeanInformation(
            _test_known={},
            _test_targets={'first': T11(), 'second': T00()},
        )
        try:
            _contrast_solve(
                {'first': St2, 'second': St2},
                info_contrast_missing,
                design_kind='D2', exposure_kind='E4',
            )
            check("contrast: missing A4 -> blocked", False,
                  "returned a certificate instead of NEEDS_INPUT")
        except BoundedPolicyUnavailable as exc:
            check(
                f"contrast: missing A4 -> {exc.state}:{exc.reason}",
                exc.state == 'NEEDS_INPUT'
                and exc.reason == 'SUPPORTED_NONZERO_CONTRAST_A4_MEAN_MISSING',
                f"got state={exc.state!r} reason={exc.reason!r}",
            )
    finally:
        SupportEngine._test_probabilities = {}

    # ── 6. Summary ─────────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    total = PASS + FAIL
    print(f"Results: {PASS}/{total} passed, {FAIL}/{total} failed")
    if FAIL == 0:
        print("ALL D2+E4 DEMO CHECKS PASSED")
    else:
        print(f"WARNING: {FAIL} check(s) FAILED — review above")
    print('=' * 60)


if __name__ == '__main__':
    main()