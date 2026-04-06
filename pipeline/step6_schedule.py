"""
local-ai-v6 — Step 6: Schedule Only
Reads:  tasks.json
Writes: cron_schedule.json

No LLM. No build. Pure deterministic scheduling.

Delay formula: max(est_seconds * CRON_FACTOR, 30)
CRON_FACTOR default = 10

The cron runner fires ONCE (initial trigger from run.py).
build_one.py self-schedules the next trigger via `at` after each task completes.
This means one cron entry starts the whole chain. Python sets every subsequent alarm.
"""
import json
import os
from pathlib import Path

HERE = Path(__file__).parent

CRON_FACTOR = int(os.environ.get("CRON_FACTOR", "10"))
FLOOR_SECONDS = 30

with open(HERE / "tasks.json", "r", encoding="utf-8") as f:
    tasks = json.load(f)

schedule = []
for task in tasks:
    est = task.get("est_seconds", 30)
    delay = max(est * CRON_FACTOR, FLOOR_SECONDS)
    schedule.append({
        "id": task["id"],
        "title": task.get("title", ""),
        "file": task.get("file", ""),
        "delay_seconds": delay,
        "est_seconds": est,
        "depends_on": task.get("depends_on", []),
        "status": "pending"
    })

with open(HERE / "cron_schedule.json", "w", encoding="utf-8") as f:
    json.dump(schedule, f, indent=2)

total = sum(s["delay_seconds"] for s in schedule)
print(f"[6/6] Done → cron_schedule.json")
print(f"       {len(schedule)} tasks | CRON_FACTOR={CRON_FACTOR} | floor={FLOOR_SECONDS}s")
print(f"       Total scheduled time: {total}s (~{total//60}m)")
