"""Independent exact replay for the binary monotone-IV LATE claim."""
from .iv_exact_verify import replay


def verify_late_result(observed,result,*,tol=1e-8):
    return replay(observed,result,True,"LATE",tol)
