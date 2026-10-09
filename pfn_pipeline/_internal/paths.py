"""Workspace resource paths independent of the process working directory."""
from pathlib import Path

RESEARCH_ROOT = Path(__file__).resolve().parents[2]
CHECKPOINTS_DIR = RESEARCH_ROOT / "checkpoints"
DEFAULT_CHECKPOINT = CHECKPOINTS_DIR / "er_estimation_demo" / "model_best.pt"
CACHE_DIR = RESEARCH_ROOT / ".cache" / "pfn_pipeline"
ESTIMATION_ROOT = Path(__file__).resolve().parent / "estimation"
DEFAULT_GRAPH = ESTIMATION_ROOT / "data" / "fixed_er_N300_p0.5_seed12345.json"
RANDOM_FUNCTION_GRAPH = ESTIMATION_ROOT / "data" / "fixed_er_N20_p0.5_seed12345.json"


def checkpoint_path(path):
    path = Path(path).expanduser()
    return path.resolve() if path.is_absolute() else (CHECKPOINTS_DIR / path).resolve()
