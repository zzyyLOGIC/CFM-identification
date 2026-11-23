"""Independent exact primal/dual and infeasibility replay for binary-IV ATE."""
from .iv_exact_verify import replay


def verify_ate_result(observed,result,*,monotonicity=False,tol=1e-7):
    return replay(observed,result,monotonicity,"ATE",tol)
