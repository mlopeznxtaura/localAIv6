"""
local-ai-v6 — Step 4: DAG Construction
Reads:  features.json
Writes: dag.json

CRITICAL GATE: If no features or empty DAG, halt the pipeline.
Do not proceed to generate tasks for a skeleton.
"""
import json
import sys
from pathlib import Path
from ollama_client import ask, check_model, safe_json

check_model()
HERE = Path(__file__).parent

with open(HERE / "features.json", "r", encoding="utf-8") as f:
    data = json.load(f)

features = data.get("features", [])
names = [f.get("name", "") for f in features if f.get("name")]

if not names:
    print("[4/6] CRITICAL: No features to build. Halting pipeline.")
    print("  → Check Step 2 (mock UI) and Step 3 (feature extraction)")
    sys.exit(1)

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

if not dag or "nodes" not in dag or "build_order" not in dag or not dag["build_order"]:
    # Fallback: flat DAG, no dependencies
    dag = {"nodes": [{"id": n, "depends_on": []} for n in names], "build_order": names}

# CRITICAL GATE: verify DAG has content
if not dag["build_order"]:
    print("[4/6] CRITICAL: DAG build_order is empty. Halting pipeline.")
    sys.exit(1)

with open(HERE / "dag.json", "w", encoding="utf-8") as f:
    json.dump(dag, f, separators=(',', ':'))

print(f"[4/6] Done → dag.json ({len(dag['build_order'])} tasks)")
