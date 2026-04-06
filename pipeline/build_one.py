"""
local-ai-v6 — build_one.py
Called by `at` daemon for each scheduled task.
One task. One process. Exits clean.

Flow:
  1. Check dependencies are complete (exit if not — at will retry via reschedule)
  2. Mark task running
  3. Generate code via Ollama (stateless call)
  4. Write file
  5. Run test
  6. Record actual_seconds vs est_seconds → stream.jsonl
  7. Compute next delay from actual (not estimated)
  8. Schedule all dependent tasks via `at`
  9. Update tasks.json
  10. Exit

The self-scheduling loop:
  run.py fires `at` for the first task only.
  Each task fires `at` for its dependents on completion.
  One cron entry starts the whole chain.
"""
import sys
import json
import time
import subprocess
import os
from datetime import datetime, timezone
from pathlib import Path
from ollama_client import ask, safe_json, strip_fences, STREAM_FILE, SESSION_ID

HERE = Path(__file__).parent
PROJECT_ROOT = HERE.parent

CRON_FACTOR = int(os.environ.get("CRON_FACTOR", "10"))
FLOOR_SECONDS = 30
MAX_RETRIES = 3

BUILD_INSTRUCTION = (
    "Write complete working code for the task. "
    "No stubs. No placeholders. No TODOs. No comments. Complete only. "
    "Return ONLY raw code. No markdown."
)


def load_tasks():
    with open(HERE / "tasks.json", "r", encoding="utf-8") as f:
        return json.load(f)

def save_tasks(tasks):
    with open(HERE / "tasks.json", "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2)

def load_tests():
    with open(HERE / "tests.json", "r", encoding="utf-8") as f:
        return json.load(f)

def load_schedule():
    p = HERE / "cron_schedule.json"
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_schedule(schedule):
    with open(HERE / "cron_schedule.json", "w", encoding="utf-8") as f:
        json.dump(schedule, f, indent=2)

def run_test(test_code: str) -> tuple:
    try:
        exec(compile(test_code, "<test>", "exec"), {})
        return True, None
    except Exception as e:
        return False, str(e)

def write_completion_record(task: dict, actual_seconds: float, passed: bool, used_fallback: bool):
    """
    Write task completion to stream.jsonl.
    Captures est vs actual so student learns estimation accuracy.
    """
    est = task.get("est_seconds", 30)
    delta = actual_seconds - est
    delta_pct = round((delta / est) * 100, 1) if est > 0 else 0

    record = {
        "instruction": (
            f"Estimate build time in seconds for task: {task.get('title', '')}\n"
            f"Description: {task.get('description', '')[:300]}"
        ),
        "input": "",
        "output": str(round(actual_seconds)),
        "metadata": {
            "type": "task_completion",
            "session_id": SESSION_ID,
            "task_id": task["id"],
            "est_seconds": est,
            "actual_seconds": round(actual_seconds, 2),
            "delta_seconds": round(delta, 2),
            "delta_pct": delta_pct,
            "passed_test": passed,
            "used_fallback": used_fallback,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    }
    with open(STREAM_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

def schedule_dependent(dep_id: str, tasks: list, schedule: list, running_avg_ratio: float):
    """
    Schedule a dependent task via `at`.
    Delay uses actual-adjusted ratio if available, else est × CRON_FACTOR.
    Hard floor: 30s.
    """
    dep_task = next((t for t in tasks if t["id"] == dep_id), None)
    if not dep_task:
        return
    if dep_task.get("status") in ("running", "complete"):
        return

    # Check all of dep_task's own dependencies are complete
    dep_tasks_statuses = {t["id"]: t.get("status") for t in tasks}
    dep_depends = dep_task.get("depends_on", [])
    if not all(dep_tasks_statuses.get(d) == "complete" for d in dep_depends):
        return  # not ready yet — another completing task will trigger it

    est = dep_task.get("est_seconds", 30)
    adjusted_est = est * running_avg_ratio
    delay = max(int(adjusted_est * CRON_FACTOR), FLOOR_SECONDS)

    pipeline_dir = str(HERE)
    env_str = f"LAV6_SESSION_ID={SESSION_ID} CRON_FACTOR={CRON_FACTOR}"
    cmd = f"cd {pipeline_dir} && {env_str} python3 build_one.py {dep_id}"

    try:
        at_input = f"{cmd}\n"
        proc = subprocess.Popen(
            ["at", f"now + {delay} seconds"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        proc.communicate(input=at_input.encode())
        print(f"  → scheduled {dep_id} in {delay}s (adj_est={adjusted_est:.0f}s × {CRON_FACTOR})")

        # Update schedule record
        for s in schedule:
            if s["id"] == dep_id:
                s["delay_seconds"] = delay
                s["status"] = "scheduled"
    except FileNotFoundError:
        # `at` not available — fallback: subprocess with sleep
        print(f"  → `at` not found, using sleep fallback for {dep_id}")
        script = f"sleep {delay} && cd {pipeline_dir} && {env_str} python3 build_one.py {dep_id}"
        subprocess.Popen(["bash", "-c", script], start_new_session=True)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 build_one.py <TASK_ID>")
        sys.exit(1)

    # Change to project root so relative paths (output/, training_data/, etc.) work correctly
    os.chdir(PROJECT_ROOT)

    task_id = sys.argv[1]
    tasks = load_tasks()
    tests = load_tests()
    schedule = load_schedule()

    task = next((t for t in tasks if t["id"] == task_id), None)
    if not task:
        print(f"[build_one] Task {task_id} not found")
        sys.exit(1)

    if task.get("status") == "complete":
        print(f"[build_one] {task_id} already complete — skipping")
        sys.exit(0)

    # Check dependencies
    dep_statuses = {t["id"]: t.get("status") for t in tasks}
    unmet = [d for d in task.get("depends_on", []) if dep_statuses.get(d) != "complete"]
    if unmet:
        print(f"[build_one] {task_id} waiting on: {unmet} — will be rescheduled by dependencies")
        sys.exit(0)

    # Mark running
    task["status"] = "running"
    save_tasks(tasks)

    test = next((t for t in tests if t["task_id"] == task_id), None)
    test_code = test.get("test_code", "pass") if test else "pass"

    file_path = task.get("file", "")
    if not file_path.startswith("output/"):
        file_path = f"output/{file_path}"
    abs_path = PROJECT_ROOT / file_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)

    # Build loop
    build_start = time.time()
    success = False
    used_fallback = False

    for attempt in range(1, MAX_RETRIES + 1):
        print(f"[build_one] {task_id} attempt {attempt}/{MAX_RETRIES}...")

        user = (
            BUILD_INSTRUCTION + "\n\n"
            f"Task: {task.get('title', '')}\n"
            f"File: {file_path}\n"
            f"Description: {task.get('description', '')}"
        )
        raw, fb = ask(6, "build_execution", task_id, user, budget=2048,
                      call_index=attempt - 1)
        used_fallback = used_fallback or fb

        code = strip_fences(raw)
        if code.startswith("python\n"):
            code = code[7:]

        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(code)

        passed, err = run_test(test_code)
        if passed:
            print(f"  ✓ passed")
            success = True
            break
        else:
            print(f"  ✗ {err}")

    actual_seconds = time.time() - build_start

    # Write completion record (est vs actual → student learns estimation)
    write_completion_record(task, actual_seconds, success, used_fallback)

    # Update task status
    task["status"] = "complete" if success else "failed"
    task["actual_seconds"] = round(actual_seconds, 2)
    save_tasks(tasks)

    # Update schedule entry
    for s in schedule:
        if s["id"] == task_id:
            s["status"] = task["status"]
            s["actual_seconds"] = task["actual_seconds"]
    save_tasks(tasks)

    if not success:
        print(f"[build_one] {task_id} FAILED after {MAX_RETRIES} attempts")
        save_schedule(schedule)
        sys.exit(1)

    print(f"[build_one] {task_id} complete in {actual_seconds:.1f}s (est={task.get('est_seconds',30)}s)")

    # Compute running accuracy ratio for delay adjustment
    completed = [t for t in tasks if t.get("status") == "complete" and "actual_seconds" in t]
    if completed:
        ratios = [(t["actual_seconds"] / max(t.get("est_seconds", 30), 1)) for t in completed]
        running_avg_ratio = sum(ratios) / len(ratios)
    else:
        running_avg_ratio = 1.0

    print(f"  running_avg_ratio={running_avg_ratio:.2f} (actual/est across {len(completed)} tasks)")

    # Self-schedule dependents
    dependents = [t["id"] for t in tasks if task_id in t.get("depends_on", [])]
    for dep_id in dependents:
        schedule_dependent(dep_id, tasks, schedule, running_avg_ratio)

    # Also check root-level tasks with no dependencies that are still pending
    if not dependents:
        for t in tasks:
            if t.get("status") == "pending" and not t.get("depends_on"):
                if t["id"] != task_id:
                    schedule_dependent(t["id"], tasks, schedule, running_avg_ratio)

    save_schedule(schedule)

    # Mandatory zip after ALL tasks complete
    all_done = all(t.get("status") in ("complete", "failed") for t in tasks)
    if all_done:
        import zipfile
        zip_path = PROJECT_ROOT / "output.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            output_dir = PROJECT_ROOT / "output"
            for root, _, files in os.walk(output_dir):
                for fname in files:
                    full = Path(root) / fname
                    arcname = full.relative_to(PROJECT_ROOT)
                    zf.write(full, arcname)
        print(f"\n[build_one] ALL TASKS DONE → output.zip written")

        # Optional GitHub push
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True, text=True, timeout=5, cwd=str(PROJECT_ROOT)
            )
            if result.returncode == 0:
                subprocess.run(["git", "add", "output/"], cwd=str(PROJECT_ROOT), timeout=10)
                subprocess.run(["git", "commit", "-m", "local-ai-v6: build output"],
                               cwd=str(PROJECT_ROOT), timeout=10)
                push = subprocess.run(["git", "push"], capture_output=True, text=True,
                                      timeout=30, cwd=str(PROJECT_ROOT))
                if push.returncode == 0:
                    print(f"[build_one] ✓ Pushed to git remote")
        except Exception:
            pass


if __name__ == "__main__":
    main()
