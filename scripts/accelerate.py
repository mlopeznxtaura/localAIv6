"""
local-ai-v6 — scripts/accelerate.py
Mark a task complete instantly — skips remaining delay and triggers dependents now.
Usage: python3 scripts/accelerate.py T001
"""
import sys
import json
import subprocess
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
PIPELINE_DIR = PROJECT_ROOT / "pipeline"


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/accelerate.py <TASK_ID>")
        sys.exit(1)

    task_id = sys.argv[1]
    tasks_file = PIPELINE_DIR / "tasks.json"

    if not tasks_file.exists():
        print("No tasks.json found.")
        sys.exit(1)

    tasks = json.load(open(tasks_file))
    task = next((t for t in tasks if t["id"] == task_id), None)

    if not task:
        print(f"Task {task_id} not found.")
        sys.exit(1)

    if task.get("status") == "complete":
        print(f"{task_id} already complete.")
        sys.exit(0)

    task["status"] = "complete"
    task["actual_seconds"] = task.get("est_seconds", 30)  # treat est as actual on accelerate

    with open(tasks_file, "w") as f:
        json.dump(tasks, f, indent=2)

    print(f"✓ {task_id} marked complete (accelerated)")

    # Immediately fire dependents
    session_id = os.environ.get("LAV6_SESSION_ID", "accelerated")
    cron_factor = os.environ.get("CRON_FACTOR", "10")
    dependents = [t["id"] for t in tasks if task_id in t.get("depends_on", [])]

    for dep_id in dependents:
        dep = next((t for t in tasks if t["id"] == dep_id), None)
        if not dep or dep.get("status") in ("complete", "running"):
            continue
        # Check all deps of dep are complete
        dep_statuses = {t["id"]: t.get("status") for t in tasks}
        if not all(dep_statuses.get(d) == "complete" for d in dep.get("depends_on", [])):
            continue
        cmd = f"cd {PIPELINE_DIR} && LAV6_SESSION_ID={session_id} CRON_FACTOR={cron_factor} python3 build_one.py {dep_id}"
        try:
            proc = subprocess.Popen(["at", "now + 5 seconds"], stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            proc.communicate(input=(cmd + "\n").encode())
            print(f"  → {dep_id} scheduled in 5s")
        except FileNotFoundError:
            subprocess.Popen(["bash", "-c", f"sleep 5 && {cmd}"], start_new_session=True)
            print(f"  → {dep_id} scheduled in 5s (sleep fallback)")


if __name__ == "__main__":
    main()
