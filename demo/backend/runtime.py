"""Import this repository's ID packages; no full-pipeline dependencies."""
from pathlib import Path
import importlib
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]

def application_root():
    """Locate the receipt adapter in a flat checkout or the nested development tree."""
    if (PROJECT_ROOT / "estimate_intake.py").is_file():
        return PROJECT_ROOT
    if PROJECT_ROOT.name == "identification" and (PROJECT_ROOT.parent / "estimate_intake.py").is_file():
        return PROJECT_ROOT.parent
    raise RuntimeError("Identification checkout is missing estimate_intake.py")

def identification_modules():
    if not (PROJECT_ROOT/'cfm_id/project.py').is_file():
        raise RuntimeError('IDENTIFICATION_SOURCE_MISSING')
    root = str(PROJECT_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    for name in ('cfm_id', 'cfm_id_llm', 'pfn_pipeline'):
        module = importlib.import_module(name)
        if not Path(module.__file__).resolve().is_relative_to(PROJECT_ROOT):
            raise RuntimeError(f'CONFLICTING_BACKEND_IMPORT: {name}')
    from cfm_id import project, business_intake, business_dispatch
    return project, business_intake, business_dispatch
