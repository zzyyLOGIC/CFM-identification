"""Run offline checks; live-response archives are optional."""
from pathlib import Path
import argparse, os, subprocess, sys

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--integration',action='store_true',help='Compatibility option. The full ID integration suite always runs.')
    p.parse_args();root=Path(__file__).resolve().parents[1]
    env=os.environ.copy();env.update(PYTHONDONTWRITEBYTECODE='1',PYTHONUTF8='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    command=[sys.executable,'-m','pytest','tests','tests_gateway','evaluation/task6/tests','-q']
    return subprocess.call(command,cwd=root,env=env)

if __name__=='__main__':raise SystemExit(main())
