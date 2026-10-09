"""Run student_work/task*/test_*.py in a separate pytest process per task."""
from pathlib import Path
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    task_dirs = sorted(p for p in (root / "student_work").glob("task*") if p.is_dir())
    if not task_dirs:
        print("No student task directories yet; skipping student tests.", flush=True)
        return 0

    failed = []
    for task_dir in task_dirs:
        tests = sorted(task_dir.glob("test_*.py"))
        label = task_dir.relative_to(root).as_posix()
        if not tests:
            print(f"FAIL {label}: add test_rule.py or another test_*.py file.", flush=True)
            failed.append(label)
            continue
        print(f"Running {label}", flush=True)
        # Keep each task's local support/rule/test modules isolated from other tasks.
        result = subprocess.run(
            [sys.executable, "-B", "-m", "pytest", "-q", *map(str, tests)],
            cwd=root,
        )
        if result.returncode != 0:
            failed.append(label)

    if failed:
        print("Failed student tasks: " + ", ".join(failed), flush=True)
        return 1
    print(f"Passed all {len(task_dirs)} student tasks.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
