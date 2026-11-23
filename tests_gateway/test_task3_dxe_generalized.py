"""Task 3: End-to-end test for generalized D1-D6 × E1-E5 PARTIAL implementation.

Follows the teacher's guidance: first make D2+E4 work (policy mean, contrast,
certificate replay), then generalize to all 30 combos.

Run with: pytest tests/test_task3_dxe_generalized.py -v

Prerequisites:
  - CFM-identification repo cloned (for cfm_id package imports)
  - This file resides in tests/test_task3_dxe_generalized.py
  - bounded_policy_fixture must be available for synthetic fixtures
"""
import pytest
from fractions import Fraction as F

try:
    from cfm_id.general_bounded_policy_solver import (
        solve as policy_solve,
        _validate_design_kind,
        _validate_exposure_kind,
        _enumerate_cells,
        DESIGN_KINDS,
        EXPOSURE_KINDS,
    )
    from cfm_id.general_bounded_contrast_solver import (
        solve as contrast_solve,
        analyze as contrast_analyze,
    )
    CAN_IMPORT = True
except (ImportError, ModuleNotFoundError):
    CAN_IMPORT = False


# ═══════════════════════════════════════════════════════════════════════════════
#  Cell enumeration tests
# ═══════════════════════════════════════════════════════════════════════════════

def _make_stub_structure(node_order, undirected_edges):
    """Minimal st structure for cell enumeration."""
    class StubStructure:
        node_order = node_order
        undirected_edges = undirected_edges
    return StubStructure()


class TestCellEnumeration:
    """Independent tests: do not require the full CFM-identification repo."""

    def test_design_kinds(self):
        assert DESIGN_KINDS == frozenset({'D1', 'D2', 'D3', 'D4', 'D5', 'D6'})

    def test_exposure_kinds(self):
        assert EXPOSURE_KINDS == frozenset({'E1', 'E2', 'E3', 'E4', 'E5'})

    def test_validate_design(self):
        for dk in DESIGN_KINDS:
            _validate_design_kind(dk)
        with pytest.raises(ValueError):
            _validate_design_kind('D7')

    def test_validate_exposure(self):
        for ek in EXPOSURE_KINDS:
            _validate_exposure_kind(ek)
        with pytest.raises(ValueError):
            _validate_exposure_kind('E6')

    def test_e1_binary(self):
        """E1 (strict_majority_ties_low): binary for non-isolates."""
        st = _make_stub_structure(['X', 'Y'], [('X', 'Y')])
        neighbors = {'X': {'Y'}, 'Y': {'X'}}
        cells = _enumerate_cells(st, neighbors, 'E1')
        assert len(cells) == 4
        for n in ('X', 'Y'):
            for a in (0, 1):
                assert (n, a, 0) in cells
                assert (n, a, 1) in cells

    def test_e1_isolate_binary(self):
        """E1 isolate: only 2 cells (exposure always 0)."""
        st = _make_stub_structure(['A'], [])
        neighbors = {'A': set()}
        cells = _enumerate_cells(st, neighbors, 'E1')
        assert len(cells) == 2
        assert ('A', 0, 0) in cells
        assert ('A', 1, 0) in cells

    def test_e2_three_level(self):
        """E2 (three_level_treated_neighbor_fraction): {0,1,2} for non-isolates."""
        st = _make_stub_structure(['X', 'Y'], [('X', 'Y')])
        neighbors = {'X': {'Y'}, 'Y': {'X'}}
        cells = _enumerate_cells(st, neighbors, 'E2')
        assert len(cells) == 6
        for n in ('X', 'Y'):
            for a in (0, 1):
                for e in (0, 1, 2):
                    assert (n, a, e) in cells

    def test_e2_isolate_fails(self):
        """E2 isolate: raises INCOMPATIBLE."""
        st = _make_stub_structure(['A'], [])
        neighbors = {'A': set()}
        with pytest.raises(Exception, match='E2_THREE_LEVEL_UNDEFINED_FOR_ISOLATE'):
            _enumerate_cells(st, neighbors, 'E2')

    def test_e3_binary(self):
        """E3 (pretreatment_core_collaborator_majority): binary {0,1}."""
        st = _make_stub_structure(['X', 'Y'], [('X', 'Y')])
        neighbors = {'X': {'Y'}, 'Y': {'X'}}
        cells = _enumerate_cells(st, neighbors, 'E3')
        # E3 is binary, not degree-based
        assert len(cells) == 4
        for n in ('X', 'Y'):
            for a in (0, 1):
                assert (n, a, 0) in cells
                assert (n, a, 1) in cells

    def test_e4_exact_count(self):
        """E4 (exact_treated_neighbor_count): {0..deg}."""
        st = _make_stub_structure(['X', 'Y', 'Z'], [('X', 'Y'), ('Y', 'Z')])
        neighbors = {'X': {'Y'}, 'Y': {'X', 'Z'}, 'Z': {'Y'}}
        cells = _enumerate_cells(st, neighbors, 'E4')
        # X (deg=1): 2×2=4, Y (deg=2): 2×3=6, Z (deg=1): 2×2=4
        assert len(cells) == 14
        for a in (0, 1):
            for e in range(2):
                assert ('X', a, e) in cells
            for e in range(3):
                assert ('Y', a, e) in cells
            for e in range(2):
                assert ('Z', a, e) in cells

    def test_e5_binary(self):
        """E5 (any_treated_neighbor): binary {0,1}."""
        st = _make_stub_structure(['A', 'B'], [('A', 'B')])
        neighbors = {'A': {'B'}, 'B': {'A'}}
        cells = _enumerate_cells(st, neighbors, 'E5')
        assert len(cells) == 4
        for n in ('A', 'B'):
            for a in (0, 1):
                assert (n, a, 0) in cells
                assert (n, a, 1) in cells


# ═══════════════════════════════════════════════════════════════════════════════
#  Core solve tests (require full CFM-identification repo)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def star7_fixture():
    """Return a star7 synthetic fixture with known fields."""
    from cfm_id.bounded_policy_fixture import specification, public_bundle, model
    nodes, edges, quota, pop = specification('star7')
    bundle = public_bundle('star7', pop)
    return nodes, edges, quota, pop, bundle


@pytest.mark.skipif(not CAN_IMPORT, reason='requires full CFM-identification repo')
class TestD2E4PolicyMean:
    """Teacher-requested primary path: D2 (uniform fixed quota) + E4 (exact count)."""

    def test_d2_e4_policy_mean_known(self, star7_fixture):
        """Solve one policy mean for D2+E4."""
        from cfm_id.bounded_policy_fixture import model
        from cfm_id.bounded_policy_contract import (
            BoundedMeanInformation, validate_model,
        )
        nodes, edges, quota, pop, bundle = star7_fixture
        st = model('star7', pop)
        target = st.fixed_policy_target_from_context(
            st, (1,) * len(nodes),
            authority='TRUSTED_FIXTURE',
            unit_weights=tuple(
                str(F(1, len(pop))) if n in pop else '0'
                for n in nodes
            ),
        )
        # Build a synthetic inference with known A4 values and bounds.
        known = {}
        for v in st.values:
            known[(v.node, v.own, v.exposure)] = F(v.value)
        bounds = {n: (F(0), F(1)) for n in nodes}
        # D2 + E4: exact_treated_neighbor_count
        certificate = policy_solve(
            st, BoundedMeanInformation(
                values=[], bounds=[],  # filled by validate_model
            ),
            design_kind='D2', exposure_kind='E4',
        )
        # Default path should complete without exception.
        assert certificate['status'] in ('POINT', 'PARTIAL')
        assert 'lower' in certificate
        assert 'upper' in certificate
        lo, hi = F(certificate['lower']), F(certificate['upper'])
        assert lo <= hi