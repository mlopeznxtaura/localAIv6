"""
local-ai-v6 — Step 5: Task & Test Generation + Time Estimation
Reads:  dag.json, compressed_intent.txt, grounded_context.json
Writes: tasks.json, tests.json

Per-feature loop:
  A: Generate task spec + est_seconds (LLM estimates build time)
  B: Generate test immediately
  C: compile() validate — replace with existence check on SyntaxError

est_seconds is written into tasks.json.
build_one.py records actual_seconds at completion.
Delta written to stream.jsonl for student to learn estimation accuracy.
"""
import json
from pathlib import Path
from ollama_client import ask, check_model, safe_json

check_model()
HERE = Path(__file__).parent

with open(HERE / "dag.json", "r", encoding="utf-8") as f:
    dag = json.load(f)
with open(HERE / "compressed_intent.txt", "r", encoding="utf-8") as f:
    intent = f.read().strip()
with open(HERE / "grounded_context.json", "r", encoding="utf-8") as f:
    ctx = json.load(f)

stack = ctx.get("grounded", {}).get("current_stack", [])
build_order = dag.get("build_order", [])

print(f"[5/6] Generating {len(build_order)} tasks + tests...")

tasks = []
tests = []

for i, feature_name in enumerate(build_order):
    tid = f"T{str(i + 1).zfill(3)}"

    # Sub-step A: task spec + est_seconds
    user_a = (
        f"Generate ONE atomic build task for: {feature_name}\n"
        f"App: {intent}\nStack: {', '.join(stack) if stack else 'any'}\n\n"
        f"Return ONLY: {{\"id\":\"{tid}\",\"title\":\"...\",\"file\":\"output/path/file.ext\","
        f"\"description\":\"complete spec\",\"depends_on\":[],\"status\":\"pending\","
        f"\"est_seconds\":30}}\n"
        f"est_seconds = your best estimate of how many seconds to build this file."
    )
    raw_a, fb_a = ask(5, "task_generation", f"{tid}_spec", user_a, budget=384, call_index=i * 3)
    task = safe_json(raw_a, None)
    if not task or "file" not in task:
        task = {
            "id": tid,
            "title": feature_name,
            "file": f"output/{feature_name.lower().replace(' ', '_')}.py",
            "description": f"Implement {feature_name}",
            "depends_on": [],
            "status": "pending",
            "est_seconds": 30
        }
    task["id"] = tid
    task.setdefault("est_seconds", 30)

    # Sub-step B: test — only receives task ID + file path (not full spec)
    user_b = (
        f"Write a Python test that verifies task {tid} was completed. "
        f"Assert file exists and contains correct logic. "
        f"Return ONLY: {{\"task_id\":\"{tid}\",\"test_code\":\"import os\\nassert os.path.exists('...')\"}}\n"
        f"File: {task.get('file', '')}"
    )
    raw_b, fb_b = ask(5, "test_generation", f"{tid}_test", user_b, budget=256, call_index=i * 3 + 1)
    test = safe_json(raw_b, None)
    if not test or "test_code" not in test:
        test = {
            "task_id": tid,
            "test_code": f"import os\nassert os.path.exists('{task.get('file', '')}'), 'Missing'"
        }
    test["task_id"] = tid

    # Sub-step C: compile() validate — no LLM, pure Python
    test_code = test.get("test_code", "pass")
    try:
        compile(test_code, "<validate>", "exec")
        validation = "ok"
    except SyntaxError:
        validation = "syntax_error_replaced"
        test["test_code"] = f"import os\nassert os.path.exists('{task.get('file', '')}'), 'File missing'"

    tasks.append(task)
    tests.append(test)
    print(f"  {tid} — {feature_name[:40]} est={task['est_seconds']}s [{validation}]")

with open(HERE / "tasks.json", "w", encoding="utf-8") as f:
    json.dump(tasks, f, indent=2)
with open(HERE / "tests.json", "w", encoding="utf-8") as f:
    json.dump(tests, f, indent=2)

print(f"[5/6] Done → {len(tasks)} tasks, {len(tests)} tests")
