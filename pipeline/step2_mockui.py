"""
local-ai-v6 — Step 2: Mock UI Structure (JSON)
Reads:  compressed_intent.txt, grounded_context.json
Writes: mock_ui.json

Outputs a structured JSON description of the UI — pages, components, interactions.
No HTML. No LLM token waste on markup. Pure data.
"""
import json
from pathlib import Path
from ollama_client import ask, check_model, safe_json

check_model()
HERE = Path(__file__).parent

with open(HERE / "compressed_intent.txt", "r", encoding="utf-8") as f:
    intent = f.read().strip()

with open(HERE / "grounded_context.json", "r", encoding="utf-8") as f:
    ctx = json.load(f)

stack = ctx.get("grounded", {}).get("current_stack", [])
stack_hint = f"Preferred stack: {', '.join(stack)}. " if stack else ""

print("[2/6] Generating mock UI structure (JSON)...")

user = (
    "Return a JSON object describing the UI structure for this app. "
    "Format: {\"pages\":[{\"name\":\"...\",\"components\":[{\"type\":\"button|input|list|chart|form|table|card\",\"label\":\"...\",\"props\":{}}],\"interactions\":[{\"trigger\":\"...\",\"action\":\"...\"}]}]}. "
    f"{stack_hint}"
    "Include all pages, components, and user interactions. "
    "Return ONLY valid minified JSON. No markdown, no explanation.\n\n"
    f"App: {intent}"
)
raw_out, fb = ask(2, "mock_ui_generation", "generate", user, budget=2048, call_index=0)
result = safe_json(raw_out, None)

if not result or "pages" not in result:
    # Fallback: minimal structure from intent
    result = {
        "pages": [{
            "name": "Main",
            "components": [{"type": "card", "label": intent, "props": {}}],
            "interactions": []
        }]
    }

with open(HERE / "mock_ui.json", "w", encoding="utf-8") as f:
    json.dump(result, f, separators=(',', ':'))

total_components = sum(len(p.get("components", [])) for p in result.get("pages", []))
print(f"[2/6] Done → mock_ui.json ({len(result['pages'])} pages, {total_components} components)")
