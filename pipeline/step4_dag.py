"""
local-ai-v6 — Step 4: DAG Construction
Reads:  features.json
Writes: dag.json
"""
import json
from pathlib import Path
from ollama_client import ask, check_model, safe_json

check_model()
HERE = Path(__file__).parent

with open(HERE / "features.json", "r", encoding="utf-8") as f:
    data = json.load(f)

names = [f.get("name", "") for f in data.get("features", []) if f.get("name")]
compact = json.dumps(names, separators=(',', ':'))

print(f"[4/6] Building DAG for {len(names)} features...")

user = (
    "Given this feature list, return a build dependency DAG. "
    "Format: {\"nodes\":[{\"id\":\"...\",\"depends_on\":[]}],\"build_order\":[\"...\"]}. "
    "Topologically sorted — dependencies first. "
    "Return ONLY valid minified JSON.\n\n" + compact
)
raw_out, fb = ask(4, "dag_construction", "build", user, budget=1024, call_index=0)
dag = safe_json(raw_out, None)
if not dag or "nodes" not in dag or "build_order" not in dag:
    dag = {"nodes": [{"id": n, "depends_on": []} for n in names], "build_order": names}

with open(HERE / "dag.json", "w", encoding="utf-8") as f:
    json.dump(dag, f, separators=(',', ':'))

print(f"[4/6] Done → dag.json ({len(dag['build_order'])} tasks)")
