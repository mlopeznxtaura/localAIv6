"""
local-ai-v6 — run.py
Runs steps 0-6, then fires ONE `at` trigger per root task (no dependencies).
After that, build_one.py self-schedules everything.

Usage:
  python3 run.py "your intent"
  python3 run.py              (reads user_prompt.txt)
"""
import subprocess
import sys
import os
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
PROJECT_ROOT = HERE.parent

STEPS = [
    (0, "step0_ground.py",   "Web Grounding"),
    (1, "step1_compress.py", "Prompt Compression"),
    (2, "step2_mockui.py",   "Mock UI Generation"),
    (3, "step3_parse.py",    "Feature Parsing"),
    (4, "step4_dag.py",      "DAG Construction"),
    (5, "step5_tasks.py",    "Task & Test Generation"),
    (6, "step6_schedule.py", "Schedule"),
]


def fire_initial_triggers(session_id: str):
    """Fire `at` trigger for root tasks (no dependencies). Everything else self-schedules."""
    tasks_file = HERE / "tasks.json"
    schedule_file = HERE / "cron_schedule.json"

    if not tasks_file.exists() or not schedule_file.exists():
        print("[run] WARNING: tasks.json or cron_schedule.json missing — skipping trigger")
        return

    with open(tasks_file) as f:
        tasks = json.load(f)
    with open(schedule_file) as f:
        schedule = json.load(f)

    cron_factor = os.environ.get("CRON_FACTOR", "10")
    aggressiveness = os.environ.get("COMPRESSION_AGGRESSIVENESS", "20")
    pipeline_dir = str(HERE)

    roots = [s for s in schedule if not s.get("depends_on")]
    print(f"\n[run] Firing initial triggers for {len(roots)} root task(s)...")

    for entry in roots:
        delay = entry.get("delay_seconds", 30)
        task_id = entry["id"]
        env_str = f"LAV6_SESSION_ID={session_id} CRON_FACTOR={cron_factor} COMPRESSION_AGGRESSIVENESS={aggressiveness}"
        cmd = f"cd {pipeline_dir} && {env_str} python3 build_one.py {task_id}"

        try:
            proc = subprocess.Popen(
                ["at", f"now + {delay} seconds"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            proc.communicate(input=(cmd + "\n").encode())
            print(f"  → {task_id} scheduled in {delay}s via `at`")
        except FileNotFoundError:
            print(f"  → `at` not found, using sleep fallback for {task_id}")
            script = f"sleep {delay} && cd {pipeline_dir} && {env_str} python3 build_one.py {task_id}"
            subprocess.Popen(["bash", "-c", script], start_new_session=True)


def main():
    session_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    env = {
        **os.environ,
        "LAV6_SESSION_ID": session_id,
        "COMPRESSION_AGGRESSIVENESS": os.environ.get("COMPRESSION_AGGRESSIVENESS", "20")
    }

    os.chdir(HERE)

    if len(sys.argv) > 1:
        intent = " ".join(sys.argv[1:])
        with open(HERE / "user_prompt.txt", "w", encoding="utf-8") as f:
            f.write(intent)
        print(f"\n[local-ai-v6] Session: {session_id}")
        print(f"[local-ai-v6] Intent:  {intent}\n")
    elif not (HERE / "user_prompt.txt").exists():
        print("[local-ai-v6] ERROR: No intent. Usage: python3 run.py \"your intent\"")
        sys.exit(1)
    else:
        print(f"\n[local-ai-v6] Session: {session_id} (resuming)\n")

    for num, script, label in STEPS:
        print(f"\n{'='*48}")
        print(f"  STEP {num}/6 — {label}")
        print(f"{'='*48}")
        result = subprocess.run([sys.executable, script], cwd=HERE, env=env)
        if result.returncode != 0:
            print(f"\n[local-ai-v6] FATAL: {script} failed. Halted.")
            sys.exit(1)

    fire_initial_triggers(session_id)

    print(f"\n{'='*48}")
    print(f"  PIPELINE SCHEDULED")
    print(f"  Session:   {session_id}")
    print(f"  Schedule:  {HERE}/cron_schedule.json")
    print(f"  Training:  {PROJECT_ROOT}/training_data/stream.jsonl")
    print(f"  Monitor:   python3 scripts/status.py")
    print(f"  Accelerate: python3 scripts/accelerate.py T001")
    print(f"{'='*48}\n")


if __name__ == "__main__":
    main()
