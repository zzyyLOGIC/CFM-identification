"""Task 3: Acceptance tests for D2+E4 — fully self-contained (via conftest.py stubs).

Covers teacher's D2+E4 acceptance criteria:
  - Cell enumeration: E4 exact treated neighbor count (not binary majority)
  - E4 exposure state computation (2 treated neighbors -> 2, not 1)
  - E3 core_collaborators requirement blocks without data
  - Certificate schema: policy uses lower/upper, contrast uses cell_lower/cell_upper
  - No extra fields (design_kind, exposure_kind, route) in certificates

Run from task3-partial-extension/ via:
    python -m pytest tests_gateway/test_d2_e4_acceptance.py -v
"""
from fractions import Fraction as F
import pytest

from general_bounded_policy_solver import (
    solve as policy_solve,
    _enumerate_cells,
    _validate_design_kind, _validate_exposure_kind,
    _build_neighbors,
    _target_cells,
    DESIGN_KINDS, EXPOSURE_KINDS, EXPOSURE_SPECS,
)
from general_bounded_contrast_solver import (
    solve as contrast_solve,
    _compute_exposure_state,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  Helper
# ═══════════════════════════════════════════════════════════════════════════════

def _make_stub_structure(node_order, undirected_edges):
    class StubStructure:
        pass
    StubStructure.node_order = node_order
    StubStructure.undirected_edges = undirected_edges
    return StubStructure()


def _make_minimal_inquiry(node_order=None, edges=None):
    """Build a minimal inquiry object that passes validate_model stub."""
    node_order = node_order or ['A', 'B']
    edges = edges or [('A', 'B')]

    class Inquiry:
        pass
    Inquiry.node_order = node_order
    Inquiry.undirected_edges = edges
    return Inquiry()


# ═══════════════════════════════════════════════════════════════════════════════
#  Cell enumeration tests (self-contained)
# ═══════════════════════════════════════════════════════════════════════════════

class TestCellEnumeration:
    """Independent: exercise _enumerate_cells for all E1-E5."""

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
        st = _make_stub_structure(['X', 'Y'], [('X', 'Y')])
        neighbors = _build_neighbors(st)
        cells = _enumerate_cells(st, neighbors, 'E1')
        assert len(cells) == 8  # 2 nodes × 2 assignments × 2 exposures
        for n in ('X', 'Y'):
            for a in (0, 1):
                assert (n, a, 0) in cells
                assert (n, a, 1) in cells

    def test_e1_isolate(self):
        st = _make_stub_structure(['A'], [])
        neighbors = {'A': set()}
        cells = _enumerate_cells(st, neighbors, 'E1')
        assert len(cells) == 2
        assert ('A', 0, 0) in cells
        assert ('A', 1, 0) in cells

    def test_e2_three_level(self):
        st = _make_stub_structure(['X', 'Y'], [('X', 'Y')])
        neighbors = _build_neighbors(st)
        cells = _enumerate_cells(st, neighbors, 'E2')
        assert len(cells) == 12  # 2 nodes × 2 assignments × 3 exposure levels
        for n in ('X', 'Y'):
            for a in (0, 1):
                for e in (0, 1, 2):
                    assert (n, a, e) in cells

    def test_e2_isolate_fails(self):
        st = _make_stub_structure(['A'], [])
        neighbors = {'A': set()}
        with pytest.raises(Exception, match='E2_THREE_LEVEL_UNDEFINED_FOR_ISOLATE'):
            _enumerate_cells(st, neighbors, 'E2')

    def test_e3_binary(self):
        st = _make_stub_structure(['X', 'Y'], [('X', 'Y')])
        neighbors = _build_neighbors(st)
        cells = _enumerate_cells(st, neighbors, 'E3')
        assert len(cells) == 8  # 2 nodes × 2 assigments × 2 exposures
        for n in ('X', 'Y'):
            assert sorted(set(c[2] for c in cells if c[0] == n)) == [0, 1]

    def test_e4_exact_count(self):
        """E4: exposure = {0..deg}, NOT binary."""
        st = _make_stub_structure(['X', 'Y', 'Z'], [('X', 'Y'), ('Y', 'Z')])
        neighbors = _build_neighbors(st)
        cells = _enumerate_cells(st, neighbors, 'E4')
        assert len(cells) == 14  # X:4, Y:6, Z:4
        for n, deg in [('X', 1), ('Y', 2), ('Z', 1)]:
            exposures = sorted(set(c[2] for c in cells if c[0] == n))
            assert exposures == list(range(deg + 1)), \
                f"Node {n}: exposures {exposures} != {list(range(deg+1))}"

    def test_e4_isolate(self):
        """E4 isolate: deg=0 -> only 2 cells, both e=0."""
        st = _make_stub_structure(['A'], [])
        neighbors = {'A': set()}
        cells = _enumerate_cells(st, neighbors, 'E4')
        assert len(cells) == 2
        assert all(c[2] == 0 for c in cells)

    def test_e5_binary(self):
        st = _make_stub_structure(['A', 'B'], [('A', 'B')])
        neighbors = _build_neighbors(st)
        cells = _enumerate_cells(st, neighbors, 'E5')
        assert len(cells) == 8  # 2 nodes × 2 assignments × 2 exposures

    def test_d2_e4_cell_count_chain4(self):
        st = _make_stub_structure(['A', 'B', 'C', 'D'],
                                    [('A', 'B'), ('B', 'C'), ('C', 'D')])
        neighbors = _build_neighbors(st)
        cells = _enumerate_cells(st, neighbors, 'E4')
        assert len(cells) == 20  # 4+6+6+4


# ═══════════════════════════════════════════════════════════════════════════════
#  E4 exact_count verification — teacher's Issue 2: not binary majority
# ═══════════════════════════════════════════════════════════════════════════════

class TestE4ExactCount:
    """Verify E4 is NEVER treated as binary majority anywhere."""

    def test_e4_exposure_spec(self):
        assert EXPOSURE_SPECS['E4'] == ('exact_treated_neighbor_count', None)

    def test_e4_two_treated_neighbors_not_majority(self):
        """2/2 treated -> exposure=2, NOT 1 (teacher's key example)."""
        neighbors = {'X': {'A', 'B'}, 'A': {'X'}, 'B': {'X'}}
        policy = {'X': 0, 'A': 1, 'B': 1}
        e = _compute_exposure_state('X', policy, neighbors, 'E4', None)
        assert e == 2, f"E4: 2 treated neighbors -> {e}, expected 2"
        assert e != 1, "E4: 2 treated neighbors must NOT collapse to majority=1"

    def test_e4_one_treated_neighbor(self):
        """1/2 treated -> exposure=1 (exact count)."""
        neighbors = {'X': {'A', 'B'}, 'A': {'X'}, 'B': {'X'}}
        policy = {'X': 0, 'A': 1, 'B': 0}
        e = _compute_exposure_state('X', policy, neighbors, 'E4', None)
        assert e == 1

    def test_e4_zero_treated_neighbors(self):
        """0/2 treated -> exposure=0."""
        neighbors = {'X': {'A', 'B'}, 'A': {'X'}, 'B': {'X'}}
        policy = {'X': 0, 'A': 0, 'B': 0}
        e = _compute_exposure_state('X', policy, neighbors, 'E4', None)
        assert e == 0

    def test_e4_chain_abc(self):
        """E4 in chain ABC: B has 2 neighbors, count correctly."""
        st = _make_stub_structure(['A', 'B', 'C'], [('A', 'B'), ('B', 'C')])
        neighbors = _build_neighbors(st)
        for p_a, p_b, p_c, expected_b in [(1, 0, 0, 1), (1, 0, 1, 2), (0, 0, 0, 0)]:
            policy = {'A': p_a, 'B': p_b, 'C': p_c}
            e = _compute_exposure_state('B', policy, neighbors, 'E4', None)
            assert e == expected_b, f"B with policy {policy}: E4={e}, expected {expected_b}"


# ═══════════════════════════════════════════════════════════════════════════════
#  Certificate schema alignment tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestCertificateSchema:
    """Cert field names match original bounded_*_solver format."""

    def test_policy_cert_uses_lower_upper(self):
        """Policy terms use 'lower'/'upper', never 'cell_lower'."""
        from general_bounded_policy_solver import _build_mean_bounds
        cells = [('A', 0, 0), ('A', 0, 1), ('A', 1, 0), ('A', 1, 1)]
        probs = {c: F(1, 4) for c in cells}
        known = {('A', 1, 0): F(3, 4)}
        bounds = {'A': (F(0), F(1))}
        weights = {'A': F(1)}
        rows, terms = _build_mean_bounds(cells, probs, known, bounds,
                                           weights=weights,
                                           target_cells={('A', 1, 0), ('A', 1, 1)})
        for t in terms:
            assert 'lower' in t
            assert 'upper' in t
            assert 'cell_lower' not in t
            assert 'cell_upper' not in t
            assert 'lower_contribution' not in t
            assert 'upper_contribution' not in t

    def test_contrast_cert_uses_cell_lower(self):
        """Contrast terms use 'cell_lower'/'cell_upper' + contributions."""
        import inspect
        from general_bounded_contrast_solver import solve as cs
        src = inspect.getsource(cs)
        assert 'cell_lower' in src
        assert 'cell_upper' in src
        assert 'lower_contribution' in src
        assert 'upper_contribution' in src

    def test_policy_cert_no_extra_fields(self):
        """Policy certificate dict has no design_kind, exposure_kind, or route."""
        import inspect
        from general_bounded_policy_solver import _build_certificate
        src = inspect.getsource(_build_certificate)
        for bad_key in ["'design_kind'", "'exposure_kind'", "'route'"]:
            assert bad_key not in src, f"Policy cert should not contain {bad_key}"

    def test_contrast_cert_no_extra_fields(self):
        """Contrast certificate dict has no design_kind, exposure_kind, or route."""
        import inspect
        from general_bounded_contrast_solver import solve as cs
        csrc = inspect.getsource(cs)
        # Find the certificate dict construction
        cert_start = csrc.find("certificate = dict(")
        cert_end = csrc.find("'certificate_sha256'")
        cert_src = csrc[cert_start:cert_end]
        for bad_key in ["'design_kind'", "'exposure_kind'", "'route'"]:
            assert bad_key not in cert_src


# ═══════════════════════════════════════════════════════════════════════════════
#  E3 core_collaborators required test
# ═══════════════════════════════════════════════════════════════════════════════

class TestE3CoreCollaborators:
    """E3 must block without core_collaborators data."""

    def test_e3_requires_cc(self):
        """E3 without core_collaborators -> INCOMPATIBLE."""
        from general_bounded_policy_solver import _require_core_collaborators
        from cfm_id.bounded_policy_contract import BoundedPolicyUnavailable
        st = _make_stub_structure(['A', 'B'], [('A', 'B')])
        with pytest.raises(BoundedPolicyUnavailable):
            _require_core_collaborators(st, st, 'E3')

    def test_e3_cc_spec(self):
        """EXPOSURE_SPECS['E3'] requires core_collaborators."""
        assert EXPOSURE_SPECS['E3'] == ('pretreatment_core_collaborator_majority', 'core_collaborators')


# ═══════════════════════════════════════════════════════════════════════════════
#  Full D2+E4 solve tests — end-to-end via SupportEngine._test_probabilities
# ═══════════════════════════════════════════════════════════════════════════════

def _setup_support_probs(node_order, edges, prob_map):
    """Install custom support probabilities into SupportEngine stub."""
    from pfn_pipeline._internal.identification.randomized_arm_family import SupportEngine
    neighbors = _build_neighbors(
        _make_stub_structure(node_order, edges))
    cells = _enumerate_cells(
        _make_stub_structure(node_order, edges), neighbors, 'E4')
    SupportEngine._test_probabilities = {}
    for c in cells:
        key = (c[0], c[1], c[2])
        SupportEngine._test_probabilities[key] = prob_map.get(key, F(0))


class TestD2E4PolicySolve:
    """End-to-end D2+E4 policy mean solve tests."""

    def test_policy_solve_returns_valid_certificate(self):
        """policy_solve() returns a valid certificate with lower<=upper."""
        node_order = ['A', 'B']
        edges = [('A', 'B')]
        probs = {}
        for n in node_order:
            for a in (0, 1):
                for e in (0, 1):
                    probs[(n, a, e)] = F(1, 8)
        _setup_support_probs(node_order, edges, probs)

        inquiry = _make_minimal_inquiry(node_order, edges)
        from cfm_id.bounded_policy_contract import BoundedMeanInformation
        # Target cells for policy=[1,1], E4: (A,1,1), (B,1,1)
        info = BoundedMeanInformation(_test_known={
            ('A', 1, 1): F(3, 4),
            ('B', 1, 1): F(3, 4),
        })
        cert = policy_solve(inquiry, info, design_kind='D2', exposure_kind='E4')

        assert cert['status'] in ('POINT', 'PARTIAL')
        assert F(cert['lower']) <= F(cert['upper'])
        # Certificate self-check
        expected_sha = _sha({k: v for k, v in cert.items() if k != 'certificate_sha256'})
        assert cert['certificate_sha256'] == expected_sha

    def test_policy_solve_certificate_has_correct_fields(self):
        """Certificate has required fields with correct names."""
        node_order = ['A', 'B']
        edges = [('A', 'B')]
        probs = {(n, a, e): F(1, 8) for n in node_order for a in (0, 1) for e in (0, 1)}
        _setup_support_probs(node_order, edges, probs)

        inquiry = _make_minimal_inquiry(node_order, edges)
        from cfm_id.bounded_policy_contract import BoundedMeanInformation
        info = BoundedMeanInformation(_test_known={
            ('A', 1, 1): F(3, 4),
            ('B', 1, 1): F(3, 4),
        })
        cert = policy_solve(inquiry, info, design_kind='D2', exposure_kind='E4')

        assert 'version' in cert
        assert 'theorem' in cert
        assert 'lower' in cert
        assert 'upper' in cert
        assert 'bound_terms' in cert
        assert 'certificate_sha256' in cert
        assert 'cells' in cert


class TestD2E4ContrastSolve:
    """End-to-end D2+E4 contrast solve tests."""

    def test_contrast_solve_returns_valid_certificate(self):
        """contrast_solve() returns a valid certificate."""
        node_order = ['A', 'B']
        edges = [('A', 'B')]
        probs = {(n, a, e): F(1, 8) for n in node_order for a in (0, 1) for e in (0, 1)}
        _setup_support_probs(node_order, edges, probs)

        inquiry = _make_minimal_inquiry(node_order, edges)
        from cfm_id.bounded_policy_contract import BoundedMeanInformation
        info = BoundedMeanInformation(_test_known={
            ('A', 1, 1): F(3, 4),
            ('B', 1, 1): F(3, 4),
        })
        cert = contrast_solve({'first': inquiry, 'second': inquiry},
                               info, design_kind='D2', exposure_kind='E4')

        assert F(cert['lower']) <= F(cert['upper'])
        assert 'bound_terms' in cert
        assert 'certificate_sha256' in cert

    def test_contrast_swap_symmetry(self):
        """Swapping policies: cert_21 == [-U, -L] of cert_12.

        Uses two distinct targets (all-treated vs all-control) sharing the same
        information and network.  For D2+E4 on the 2-node edge A-B:

          policy=[1,1]: A's target cell is (A,1,1)  (its only neighbor B is treated, E4=1)
                        B's target cell is (B,1,1)  (its only neighbor A is treated, E4=1)
          policy=[0,0]: A's target cell is (A,0,0)  (E4 count = 0)
                        B's target cell is (B,0,0)

        We pin (A,1,1) and (B,1,1) to 3/4 via A4, and leave (A,0,0)/(B,0,0) on
        bounds [0,1] by giving them zero support probability (which bypasses the
        analyze() "A4 must be present for positive-support nonzero cells" check).

        Independent hand-computation:
            lower_12 = 1/2*3/4 + 1/2*3/4 - 1/2*1 - 1/2*1 = -1/4
            upper_12 = 1/2*3/4 + 1/2*3/4 - 1/2*0 - 1/2*0 =  3/4
        So cert_12 = [-1/4, 3/4], and the swap must yield [-3/4, 1/4] = [-U, -L].
        """
        from cfm_id.bounded_policy_contract import BoundedMeanInformation

        node_order = ['A', 'B']
        edges = [('A', 'B')]

        # Only positive-support cells are (A,1,1) and (B,1,1).
        # Everything else defaults to support 0 via _setup_support_probs.
        _setup_support_probs(node_order, edges, {
            ('A', 1, 1): F(1, 8),
            ('B', 1, 1): F(1, 8),
        })

        class T11:
            policy_assignment = [1, 1]
            unit_weights = [F(1, 2), F(1, 2)]

        class T00:
            policy_assignment = [0, 0]
            unit_weights = [F(1, 2), F(1, 2)]

        inquiry = _make_minimal_inquiry(node_order, edges)

        info_12 = BoundedMeanInformation(
            _test_known={('A', 1, 1): F(3, 4), ('B', 1, 1): F(3, 4)},
            _test_targets={'first': T11(), 'second': T00()},
        )
        info_21 = BoundedMeanInformation(
            _test_known={('A', 1, 1): F(3, 4), ('B', 1, 1): F(3, 4)},
            _test_targets={'first': T00(), 'second': T11()},
        )

        cert_12 = contrast_solve(
            {'first': inquiry, 'second': inquiry},
            info_12, design_kind='D2', exposure_kind='E4',
        )
        cert_21 = contrast_solve(
            {'first': inquiry, 'second': inquiry},
            info_21, design_kind='D2', exposure_kind='E4',
        )

        L12, U12 = F(cert_12['lower']), F(cert_12['upper'])
        L21, U21 = F(cert_21['lower']), F(cert_21['upper'])

        # Non-degenerate interval is required for this test to be meaningful.
        assert L12 < U12, (
            f"swap-symmetry test requires L<U; got [{L12}, {U12}] "
            f"(both A4 values may be pinned incorrectly)"
        )

        # Exact hand-computed anchor (also guards against impl regressions).
        assert (L12, U12) == (F(-1, 4), F(3, 4)), (
            f"hand-computed [L,U] mismatch: got [{L12}, {U12}]"
        )

        # The swap must invert the interval exactly.
        assert (L21, U21) == (-U12, -L12), (
            f"swap symmetry broken: cert_21=[{L21},{U21}] "
            f"!= [-U,-L]=[{-U12},{-L12}]"
        )
        
    def test_same_policy_contrast_zero(self):
        """Same policy in both sides -> contrast is zero."""
        node_order = ['A', 'B']
        edges = [('A', 'B')]
        probs = {(n, a, e): F(1, 8) for n in node_order for a in (0, 1) for e in (0, 1)}
        _setup_support_probs(node_order, edges, probs)

        from cfm_id.bounded_policy_contract import BoundedMeanInformation
        info = BoundedMeanInformation(_test_known={
            ('A', 1, 1): F(3, 4),
            ('B', 1, 1): F(3, 4),
        })
        inquiry = _make_minimal_inquiry(node_order, edges)
        cert = contrast_solve({'first': inquiry, 'second': inquiry},
                               info, design_kind='D2', exposure_kind='E4')

        assert F(cert['lower']) == F('0')
        assert F(cert['upper']) == F('0')

    def test_contrast_certificate_self_consistent(self):
        """Contrast certificate SHA256 is self-consistent."""
        node_order = ['A', 'B']
        edges = [('A', 'B')]
        probs = {(n, a, e): F(1, 8) for n in node_order for a in (0, 1) for e in (0, 1)}
        _setup_support_probs(node_order, edges, probs)

        from cfm_id.bounded_policy_contract import BoundedMeanInformation
        info = BoundedMeanInformation(_test_known={
            ('A', 1, 1): F(3, 4),
            ('B', 1, 1): F(3, 4),
        })
        inquiry = _make_minimal_inquiry(node_order, edges)
        cert = contrast_solve({'first': inquiry, 'second': inquiry},
                               info, design_kind='D2', exposure_kind='E4')

        expected_sha = _sha({k: v for k, v in cert.items() if k != 'certificate_sha256'})
        assert cert['certificate_sha256'] == expected_sha

# ═══════════════════════════════════════════════════════════════════════════════
#  Independent hand-computation anchor
# ═══════════════════════════════════════════════════════════════════════════════

class TestHandComputedAnchors:
    """Each test below compares against an independently derived value.

    Graph: A—B (single edge), weights w_A = w_B = 1/2.
    D2 complete randomization on 2 nodes is trivial (the only assignments are
    {A,B} treated together or not at all), but E4's exposure value is still
    the *count* of treated neighbors, which depends on the policy.

    For policy p = [p_A, p_B]:
      A's neighbor is B, so E4 for A = p_B      -> cell (A, p_A, p_B)
      B's neighbor is A, so E4 for B = p_A      -> cell (B, p_B, p_A)

    The policy mean is therefore:
      mu(p) = w_A * m(A, p_A, p_B) + w_B * m(B, p_B, p_A)

    Each test pins the relevant cells via A4 so the mean is a definite value
    (POINT), and asserts the certificate matches exactly.
    """

    # ── Single-policy mean: treated-all ──────────────────────────────────────

    def test_policy_mean_treated_all_hand_calc(self):
        """p=[1,1]: mu = 1/2*m(A,1,1) + 1/2*m(B,1,1).

        Pin m(A,1,1)=3/4, m(B,1,1)=3/4.
        Hand calc: 1/2*3/4 + 1/2*3/4 = 3/4.  POINT at 3/4.
        """
        node_order = ['A', 'B']
        edges = [('A', 'B')]
        _setup_support_probs(node_order, edges, {
            ('A', 1, 1): F(1, 8),
            ('B', 1, 1): F(1, 8),
        })

        from cfm_id.bounded_policy_contract import BoundedMeanInformation
        inquiry = _make_minimal_inquiry(node_order, edges)
        info = BoundedMeanInformation(_test_known={
            ('A', 1, 1): F(3, 4),
            ('B', 1, 1): F(3, 4),
        })
        cert = policy_solve(inquiry, info, design_kind='D2', exposure_kind='E4')

        assert cert['status'] == 'POINT'
        assert F(cert['lower']) == F(3, 4), f"lower={cert['lower']}, expected 3/4"
        assert F(cert['upper']) == F(3, 4), f"upper={cert['upper']}, expected 3/4"

    # ── Single-policy mean: mixed policy [1,0] ───────────────────────────────
    # This is the crucial E4 test: policy [1,0] puts A and B in DIFFERENT cells
    # under E4, and a solver that collapsed E4 to binary majority would put
    # them in the wrong cells (or the same cell).

    def test_policy_mean_mixed_policy_hand_calc(self):
        """Chain A—B—C, policy [1, 0, 1].

        A's neighbor B untreated        -> E4 = 0 -> cell (A, 1, 0)
        C's neighbor B untreated        -> E4 = 0 -> cell (C, 1, 0)
        B's neighbors A and C both treated -> E4 = 2 -> cell (B, 0, 2)
          (If E4 were wrongly binary majority, B would get e=1 -> cell (B,0,1) — wrong)

        Pin A4:
            m(A,1,0) = 1/4
            m(B,0,2) = 1/2
            m(C,1,0) = 1/4
        Weights w_A = w_B = w_C = 1/3.

        Hand calc:
            1/3*1/4 + 1/3*1/2 + 1/3*1/4 = 1/12 + 1/6 + 1/12 = 1/3.  POINT at 1/3.
        """
        node_order = ['A', 'B', 'C']
        edges = [('A', 'B'), ('B', 'C')]
        
        # Only the correct target cells have positive support.
        _setup_support_probs(node_order, edges, {
            ('A', 1, 0): F(1, 12),
            ('B', 0, 2): F(1, 12),
            ('C', 1, 0): F(1, 12),
        })

        from cfm_id.bounded_policy_contract import BoundedMeanInformation

        class T101:
            policy_assignment = [1, 0, 1]
            unit_weights = [F(1, 3), F(1, 3), F(1, 3)]

        inquiry = _make_minimal_inquiry(node_order, edges)
        
        info = BoundedMeanInformation(
            _test_known={
                ('A', 1, 0): F(1, 4),
                ('B', 0, 2): F(1, 2),
                ('C', 1, 0): F(1, 4),
            },
            _test_targets={'first': T101()},
        )
        
        cert = policy_solve(inquiry, info, design_kind='D2', exposure_kind='E4')

        assert cert['status'] == 'POINT', f"expected POINT, got {cert['status']}"
        assert F(cert['lower']) == F(1, 3), f"lower={cert['lower']}, expected 1/3"
        assert F(cert['upper']) == F(1, 3), f"upper={cert['upper']}, expected 1/3"


    # ── Two-policy contrast: [1,1] - [0,0] ───────────────────────────────────

    def test_contrast_treated_all_minus_control_hand_calc(self):
        """Delta = mu([1,1]) - mu([0,0]).

        Cells (E4 on 2-node edge A—B):
          [1,1]: A -> (A,1,1), B -> (B,1,1)     coefficients  +1/2, +1/2
          [0,0]: A -> (A,0,0), B -> (B,0,0)     coefficients  -1/2, -1/2

        Pin:
          m(A,1,1) = m(B,1,1) = 3/4
          m(A,0,0) = m(B,0,0) = 1/4

        Hand calc:
          1/2*3/4 + 1/2*3/4 - 1/2*1/4 - 1/2*1/4
            = 3/8 + 3/8 - 1/8 - 1/8 = 1/2.          POINT at 1/2.
        """
        node_order = ['A', 'B']
        edges = [('A', 'B')]
        _setup_support_probs(node_order, edges, {
            ('A', 1, 1): F(1, 8),
            ('B', 1, 1): F(1, 8),
            ('A', 0, 0): F(1, 8),
            ('B', 0, 0): F(1, 8),
        })

        from cfm_id.bounded_policy_contract import BoundedMeanInformation

        class T11:
            policy_assignment = [1, 1]
            unit_weights = [F(1, 2), F(1, 2)]

        class T00:
            policy_assignment = [0, 0]
            unit_weights = [F(1, 2), F(1, 2)]

        info = BoundedMeanInformation(
            _test_known={
                ('A', 1, 1): F(3, 4), ('B', 1, 1): F(3, 4),
                ('A', 0, 0): F(1, 4), ('B', 0, 0): F(1, 4),
            },
            _test_targets={'first': T11(), 'second': T00()},
        )
        inquiry = _make_minimal_inquiry(node_order, edges)
        cert = contrast_solve(
            {'first': inquiry, 'second': inquiry},
            info, design_kind='D2', exposure_kind='E4',
        )

        assert cert['status'] == 'POINT'
        assert F(cert['lower']) == F(1, 2), f"lower={cert['lower']}, expected 1/2"
        assert F(cert['upper']) == F(1, 2), f"upper={cert['upper']}, expected 1/2"

    # ── Bounds-only policy mean: no A4, enumeration must give [0, 1] ─────────

    def test_policy_mean_bounds_only_hand_calc(self):
        """p=[1,1] with no A4 and only bounds [0,1] on every cell.

        Target cells (A,1,1) and (B,1,1), each with coefficient +1/2.
        Bounds [0,1] -> each contributes [0, 1/2].
        Hand calc: lower = 1/2*0 + 1/2*0 = 0;  upper = 1/2*1 + 1/2*1 = 1.

        The target cells are given support 0 so the analyze() A4 completeness
        check (which fires only for positive-support cells) does not short-
        circuit the bounds path.  _build_mean_bounds still emits terms for
        target cells regardless of support, so the interval is the pure
        bounds interval.
        """
        node_order = ['A', 'B']
        edges = [('A', 'B')]
        _setup_support_probs(node_order, edges, {})  # everything -> F(0)

        from cfm_id.bounded_policy_contract import BoundedMeanInformation
        inquiry = _make_minimal_inquiry(node_order, edges)
        info = BoundedMeanInformation(_test_known={})
        cert = policy_solve(inquiry, info, design_kind='D2', exposure_kind='E4')

        assert cert['status'] == 'PARTIAL'
        assert F(cert['lower']) == F(0), f"lower={cert['lower']}, expected 0"
        assert F(cert['upper']) == F(1), f"upper={cert['upper']}, expected 1"

# ═══════════════════════════════════════════════════════════════════════════════
#  Missing A4 — must stop, never silently fill
# ═══════════════════════════════════════════════════════════════════════════════

class TestMissingA4Blocked:
    """Teacher's acceptance: missing A4 -> NEEDS_INPUT, never implicit fill."""

    def test_policy_missing_target_a4_raises_needs_input(self):
        """Policy mean: target cell with positive support and no A4 -> NEEDS_INPUT.

        D2+E4 on the 2-node edge A-B, policy=[1,1]:
          A's target is (A,1,1)  (E4 count = 1)
          B's target is (B,1,1)  (E4 count = 1)
        Give both positive support, leave `known` empty -> must raise, not
        fall back to (L+U)/2 midpoint.
        """
        from cfm_id.bounded_policy_contract import (
            BoundedMeanInformation, BoundedPolicyUnavailable,
        )

        node_order = ['A', 'B']
        edges = [('A', 'B')]
        _setup_support_probs(node_order, edges, {
            ('A', 1, 1): F(1, 8),
            ('B', 1, 1): F(1, 8),
        })

        inquiry = _make_minimal_inquiry(node_order, edges)
        info = BoundedMeanInformation(_test_known={})  # empty known

        with pytest.raises(BoundedPolicyUnavailable) as exc_info:
            policy_solve(inquiry, info, design_kind='D2', exposure_kind='E4')

        exc = exc_info.value
        assert exc.state == 'NEEDS_INPUT', (
            f"expected state NEEDS_INPUT, got {exc.state!r}"
        )
        assert exc.reason == 'SUPPORTED_TARGET_A4_MEAN_MISSING', (
            f"expected SUPPORTED_TARGET_A4_MEAN_MISSING, got {exc.reason!r}"
        )

    def test_contrast_missing_a4_raises_needs_input(self):
        """Contrast: nonzero coefficient, positive support, no A4 -> NEEDS_INPUT.

        first=[1,1], second=[0,0] -> coefficients are non-zero on
        (A,1,1), (B,1,1), (A,0,0), (B,0,0).  Give the first two positive
        support; leave `known` empty -> must raise.
        """
        from cfm_id.bounded_policy_contract import (
            BoundedMeanInformation, BoundedPolicyUnavailable,
        )

        node_order = ['A', 'B']
        edges = [('A', 'B')]
        _setup_support_probs(node_order, edges, {
            ('A', 1, 1): F(1, 8),
            ('B', 1, 1): F(1, 8),
        })

        class T11:
            policy_assignment = [1, 1]
            unit_weights = [F(1, 2), F(1, 2)]

        class T00:
            policy_assignment = [0, 0]
            unit_weights = [F(1, 2), F(1, 2)]

        info = BoundedMeanInformation(
            _test_known={},
            _test_targets={'first': T11(), 'second': T00()},
        )
        inquiry = _make_minimal_inquiry(node_order, edges)

        with pytest.raises(BoundedPolicyUnavailable) as exc_info:
            contrast_solve(
                {'first': inquiry, 'second': inquiry},
                info, design_kind='D2', exposure_kind='E4',
            )

        exc = exc_info.value
        assert exc.state == 'NEEDS_INPUT', (
            f"expected state NEEDS_INPUT, got {exc.state!r}"
        )
        assert exc.reason == 'SUPPORTED_NONZERO_CONTRAST_A4_MEAN_MISSING', (
            f"expected SUPPORTED_NONZERO_CONTRAST_A4_MEAN_MISSING, got {exc.reason!r}"
        )

    def test_no_silent_midpoint_certificate(self):
        """Negative control: a certificate must NOT be returned without A4.

        Guards against regressions where a fallback to (L+U)/2 could silently
        produce `[1/2, 1/2]` (or any bounds-only midpoint) while pretending the
        A4 gap was handled.
        """
        from cfm_id.bounded_policy_contract import (
            BoundedMeanInformation, BoundedPolicyUnavailable,
        )

        node_order = ['A', 'B']
        edges = [('A', 'B')]
        _setup_support_probs(node_order, edges, {
            ('A', 1, 1): F(1, 8),
            ('B', 1, 1): F(1, 8),
        })

        inquiry = _make_minimal_inquiry(node_order, edges)
        info = BoundedMeanInformation(_test_known={})

        try:
            cert = policy_solve(inquiry, info,
                                design_kind='D2', exposure_kind='E4')
        except BoundedPolicyUnavailable:
            return  # expected path

        assert False, (
            "policy_solve returned a certificate despite missing A4: "
            f"status={cert.get('status')!r}, "
            f"[L,U]=[{cert.get('lower')},{cert.get('upper')}]. "
            "Missing A4 must raise NEEDS_INPUT, not fall back to a midpoint."
        )

# ═══════════════════════════════════════════════════════════════════════════════
#  Certificate replay tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestCertificateReplay:
    """Verify replay() passes for good cert, fails for tampered cert."""

    def test_policy_replay_passes(self):
        """policy certificate replay() returns True."""
        from cfm_id.bounded_policy_verify import replay
        node_order = ['A', 'B']
        edges = [('A', 'B')]
        probs = {(n, a, e): F(1, 8) for n in node_order for a in (0, 1) for e in (0, 1)}
        _setup_support_probs(node_order, edges, probs)

        inquiry = _make_minimal_inquiry(node_order, edges)
        from cfm_id.bounded_policy_contract import BoundedMeanInformation
        info = BoundedMeanInformation(_test_known={
            ('A', 1, 1): F(3, 4),
            ('B', 1, 1): F(3, 4),
        })
        cert = policy_solve(inquiry, info, design_kind='D2', exposure_kind='E4')

        assert replay(cert, inquiry, info) is True

    def test_policy_replay_fails_tampered(self):
        """Tampered policy certificate -> replay() returns False."""
        from cfm_id.bounded_policy_verify import replay
        node_order = ['A', 'B']
        edges = [('A', 'B')]
        probs = {(n, a, e): F(1, 8) for n in node_order for a in (0, 1) for e in (0, 1)}
        _setup_support_probs(node_order, edges, probs)

        inquiry = _make_minimal_inquiry(node_order, edges)
        from cfm_id.bounded_policy_contract import BoundedMeanInformation
        info = BoundedMeanInformation(_test_known={
            ('A', 1, 1): F(3, 4),
            ('B', 1, 1): F(3, 4),
        })
        cert = policy_solve(inquiry, info, design_kind='D2', exposure_kind='E4')

        import copy
        tampered = copy.deepcopy(cert)
        tampered['lower'] = '0/1'
        assert replay(tampered, inquiry, info) is False

    def test_contrast_replay_passes(self):
        """contrast certificate replay() returns True."""
        from cfm_id.bounded_contrast_verify import replay
        node_order = ['A', 'B']
        edges = [('A', 'B')]
        probs = {(n, a, e): F(1, 8) for n in node_order for a in (0, 1) for e in (0, 1)}
        _setup_support_probs(node_order, edges, probs)

        from cfm_id.bounded_policy_contract import BoundedMeanInformation
        info = BoundedMeanInformation(_test_known={
            ('A', 1, 1): F(3, 4),
            ('B', 1, 1): F(3, 4),
        })
        inquiry = _make_minimal_inquiry(node_order, edges)
        cert = contrast_solve({'first': inquiry, 'second': inquiry},
                               info, design_kind='D2', exposure_kind='E4')

        assert replay(cert, inquiries={'first': inquiry, 'second': inquiry},
                      information=info) is True

    def test_contrast_replay_fails_tampered(self):
        """Tampered contrast certificate -> replay() returns False."""
        from cfm_id.bounded_contrast_verify import replay
        node_order = ['A', 'B']
        edges = [('A', 'B')]
        probs = {(n, a, e): F(1, 8) for n in node_order for a in (0, 1) for e in (0, 1)}
        _setup_support_probs(node_order, edges, probs)

        from cfm_id.bounded_policy_contract import BoundedMeanInformation
        info = BoundedMeanInformation(_test_known={
            ('A', 1, 1): F(3, 4),
            ('B', 1, 1): F(3, 4),
        })
        inquiry = _make_minimal_inquiry(node_order, edges)
        cert = contrast_solve({'first': inquiry, 'second': inquiry},
                               info, design_kind='D2', exposure_kind='E4')

        import copy
        tampered = copy.deepcopy(cert)
        tampered['upper'] = '1/1'
        assert replay(tampered, inquiries={'first': inquiry, 'second': inquiry},
                      information=info) is False


# ═══════════════════════════════════════════════════════════════════════════════
#  D2/E1 regression — original combination must still work
# ═══════════════════════════════════════════════════════════════════════════════

class TestD2E1Regression:
    """D2/E1 original combination must still work as baseline."""

    def test_d2_e1_policy_solve_runs(self):
        """policy_solve(design_kind='D2', exposure_kind='E1') runs."""
        node_order = ['A', 'B']
        edges = [('A', 'B')]
        probs = {(n, a, e): F(1, 8) for n in node_order for a in (0, 1) for e in (0, 1)}
        _setup_support_probs(node_order, edges, probs)

        inquiry = _make_minimal_inquiry(node_order, edges)
        from cfm_id.bounded_policy_contract import BoundedMeanInformation
        # For E1 with policy=[1,1] on 2-node graph: target cells are (A,1,1) and (B,1,1)
        # because 1 treated neighbor > deg/2 = 0.5, so exposure = 1
        info = BoundedMeanInformation(_test_known={
            ('A', 1, 1): F(3, 4),
            ('B', 1, 1): F(3, 4),
        })
        cert = policy_solve(inquiry, info, design_kind='D2', exposure_kind='E1')
        assert cert['status'] in ('POINT', 'PARTIAL')
        assert F(cert['lower']) <= F(cert['upper'])

    def test_d2_e1_contrast_solve_runs(self):
        """contrast_solve(design_kind='D2', exposure_kind='E1') runs."""
        node_order = ['A', 'B']
        edges = [('A', 'B')]
        probs = {(n, a, e): F(1, 8) for n in node_order for a in (0, 1) for e in (0, 1)}
        _setup_support_probs(node_order, edges, probs)

        from cfm_id.bounded_policy_contract import BoundedMeanInformation
        info = BoundedMeanInformation(_test_known={
            ('A', 1, 1): F(3, 4),
            ('B', 1, 1): F(3, 4),
        })
        inquiry = _make_minimal_inquiry(node_order, edges)
        cert = contrast_solve({'first': inquiry, 'second': inquiry},
                               info, design_kind='D2', exposure_kind='E1')
        assert F(cert['lower']) <= F(cert['upper'])

    def test_d2_e1_cert_replay_passes(self):
        """D2/E1 certificate replay passes."""
        from cfm_id.bounded_policy_verify import replay
        node_order = ['A', 'B']
        edges = [('A', 'B')]
        probs = {(n, a, e): F(1, 8) for n in node_order for a in (0, 1) for e in (0, 1)}
        _setup_support_probs(node_order, edges, probs)

        inquiry = _make_minimal_inquiry(node_order, edges)
        from cfm_id.bounded_policy_contract import BoundedMeanInformation
        info = BoundedMeanInformation(_test_known={
            ('A', 1, 1): F(3, 4),
            ('B', 1, 1): F(3, 4),
        })
        cert = policy_solve(inquiry, info, design_kind='D2', exposure_kind='E1')
        assert replay(cert, inquiry, info) is True