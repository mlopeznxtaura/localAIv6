"""
local-ai-v6 — Step 2: Mock UI Generation
Reads:  compressed_intent.txt, grounded_context.json
Writes: mock_ui.html
"""
import json
from pathlib import Path
from ollama_client import ask, check_model

check_model()
HERE = Path(__file__).parent

with open(HERE / "compressed_intent.txt", "r", encoding="utf-8") as f:
    intent = f.read().strip()

with open(HERE / "grounded_context.json", "r", encoding="utf-8") as f:
    ctx = json.load(f)

stack = ctx.get("grounded", {}).get("current_stack", [])
stack_hint = f"Preferred stack: {', '.join(stack)}. " if stack else ""

print("[2/6] Generating mock UI...")

user = (
    "Return a single complete HTML file showing what this app looks like. "
    f"{stack_hint}"
    "Clean HTML, inline CSS. All buttons, forms, inputs, sections. "
    "Return ONLY raw HTML starting with <!DOCTYPE html>. No explanation. No markdown.\n\n"
    f"App: {intent}"
)
raw_out, fb = ask(2, "mock_ui_generation", "generate", user, budget=2048, call_index=0)

r = raw_out.strip()
if "```html" in r:
    r = r.split("```html")[1].split("```")[0]
elif "```" in r:
    r = r.split("```")[1].split("```")[0]
if not (r.strip().startswith("<!DOCTYPE") or r.strip().startswith("<html")):
    r = f"<!DOCTYPE html><html><body>{r}</body></html>"

with open(HERE / "mock_ui.html", "w", encoding="utf-8") as f:
    f.write(r.strip())

print("[2/6] Done → mock_ui.html")
