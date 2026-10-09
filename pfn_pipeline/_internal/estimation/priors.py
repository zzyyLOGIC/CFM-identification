"""Named training priors; checkpoint versions select a DGP without guessing."""
from pfn_pipeline._internal.paths import DEFAULT_GRAPH, RANDOM_FUNCTION_GRAPH

DEFAULT_DGP = "linear_b_random_a"
RANDOM_FUNCTIONS = "random_functions"
ER_ESTIMATION_DEMO_VERSION = "er_estimation_demo_linear_b_random_a_four_gmm_v1"
RANDOM_FUNCTION_VERSION = "causalcfm_fixed_graph_random_functions_four_gmm_v3"
VERSIONS = {DEFAULT_DGP: ER_ESTIMATION_DEMO_VERSION,
            RANDOM_FUNCTIONS: RANDOM_FUNCTION_VERSION}


def validate_dgp(dgp):
    if dgp not in VERSIONS:
        raise ValueError(f"Unknown dgp {dgp!r}; choose from {tuple(VERSIONS)}")
    return dgp


def checkpoint_dgp(state):
    for dgp, version in VERSIONS.items():
        if state.get("version") == version:
            if state.get("config", {}).get("dgp", dgp) != dgp:
                raise ValueError("Checkpoint version and configured DGP disagree")
            return dgp
    raise ValueError("Unsupported checkpoint version")


def default_graph(dgp):
    return DEFAULT_GRAPH if validate_dgp(dgp) == DEFAULT_DGP else RANDOM_FUNCTION_GRAPH


def prior_definition(dgp):
    common = ("estimands.py", "random_lpe_prior.py", "cepo.py", "causalfm_experiment/data.py")
    if validate_dgp(dgp) == DEFAULT_DGP:
        from .linear_b_dgp import generate_task, VERSION, FORMULA, A_LOW, A_HIGH
        sources = ("linear_b_dgp.py", "causalfm_dgp_v1/dgp.py", *common)
        metadata = dict(outcome_prior=dgp, formula=FORMULA,
            a_distribution=dict(name="uniform", low=A_LOW, high=A_HIGH, scope="one per dataset"))
    else:
        from .causalfm_dgp_v1 import generate_task
        from .causalfm_dgp_v1.dgp import VERSION
        sources = ("causalfm_dgp_v1/dgp.py", "causalfm_dgp_v1/outcomes.py",
            "causalfm_dgp_v1/_upstream_outcome.py", "causalfm_dgp_v1/_upstream_base.py",
            "causalfm_dgp_v1/_upstream_frontdoor.py", *common)
        metadata = dict(outcome_prior="uniform_standard_dense_composition_no_u",
                        formula="f_theta(X_i, mean_neighbor_X_i, t, e) + epsilon_i")
    return generate_task, VERSION, sources, metadata
