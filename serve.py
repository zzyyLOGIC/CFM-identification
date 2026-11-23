"""Headless entry point for the identification website and its query inbox."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
PACKAGE_ROOT = ROOT / "identification" if (ROOT / "identification" / "demo").is_dir() else ROOT
if str(PACKAGE_ROOT) != sys.path[0]:
    sys.path.insert(0, str(PACKAGE_ROOT))

from demo.backend.engine import Engine
from demo.backend.server import integrated_engine, main as serve_main, make_server


def main(argv=None):
    return serve_main(argv, default_port=8796, open_browser=False, ready_prefix="")


if __name__ == "__main__":
    main()
