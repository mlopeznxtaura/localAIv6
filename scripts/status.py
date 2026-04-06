"""
local-ai-v6 — scripts/status.py
Live task status. Run anytime during execution.
Usage: python3 scripts/status.py [--watch]
"""
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
PIPELINE_DIR = PROJECT_ROOT / "pipeline"


def show():
    tasks_file = PIPELINE_DIR / "tasks.json"
    schedule_file = PIPELINE_DIR / "cron_schedule.json"
    stream_file = PROJECT_ROOT / "training_data" / "stream.jsonl"

    if not tasks_file.exists():
        print("No tasks.json yet — run: python3 pipeline/run.py \"your intent\"")
        return

    tasks = json.load(open(tasks_file))
    schedule = {}
    if schedule_file.exists():
        for s in json.load(open(schedule_file)):
            schedule[s["id"]] = s

    counts = {"pending": 0, "running": 0, "complete": 0, "failed": 0}
    print(f"\n{'─'*56}")
    print(f"  local-ai-v6 — Task Status")
    print(f"{'─'*56}")
    for t in tasks:
        status = t.get("status", "pending")
        counts[status] = counts.get(status, 0) + 1
        est = t.get("est_seconds", "?")
        actual = t.get("actual_seconds", "")
        actual_str = f" actual={actual:.1f}s" if actual else ""
        sched = schedule.get(t["id"], {})
        delay = sched.get("delay_seconds", "?")
        icon = {"pending": "○", "running": "◉", "complete": "✓", "failed": "✗"}.get(status, "?")
        color = {"complete": "\033[92m", "failed": "\033[91m", "running": "\033[93m"}.get(status, "\033[90m")
        reset = "\033[0m"
        print(f"  {color}{icon}{reset} {t['id']:6} {status:10} est={est}s{actual_str:15} delay={delay}s  {t.get('title','')[:30]}")

    print(f"{'─'*56}")
    print(f"  ✓ {counts['complete']}  ◉ {counts['running']}  ○ {counts['pending']}  ✗ {counts['failed']}")

    # Training data stats
    if stream_file.exists():
        lines = stream_file.read_text().strip().split("\n")
        lines = [l for l in lines if l]
        clean = sum(1 for l in lines if '"used_fallback": false' in l)
        completions = sum(1 for l in lines if '"task_completion"' in l)
        print(f"\n  Training: {len(lines)} total records | {clean} clean | {completions} completions")

    zip_path = PROJECT_ROOT / "output.zip"
    if zip_path.exists():
        size = zip_path.stat().st_size // 1024
        print(f"  Output:   output.zip ({size}KB) ✓")
    print()


if __name__ == "__main__":
    watch = "--watch" in sys.argv
    if watch:
        try:
            while True:
                print("\033[2J\033[H", end="")  # clear screen
                show()
                time.sleep(3)
        except KeyboardInterrupt:
            pass
    else:
        show()
