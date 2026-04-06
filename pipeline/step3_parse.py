"""
local-ai-v6 — Step 3: Feature Parsing
Reads:  mock_ui.json
Writes: features.json

No LLM. Pure data transform — extracts features from the JSON UI structure.
Zero tokens. Zero parsing failures.
"""
import json
from pathlib import Path

HERE = Path(__file__).parent

with open(HERE / "mock_ui.json", "r", encoding="utf-8") as f:
    ui = json.load(f)

features = []
for page in ui.get("pages", []):
    page_name = page.get("name", "Main")
    for comp in page.get("components", []):
        comp_type = comp.get("type", "unknown")
        comp_label = comp.get("label", "")
        props = comp.get("props", {})

        # Build a feature description from component metadata
        description = f"{comp_type}"
        if comp_label:
            description += f": {comp_label}"
        if props:
            description += f" ({', '.join(f'{k}={v}' for k, v in props.items())})"

        # Determine inputs/outputs based on component type
        inputs = []
        outputs = []
        if comp_type in ("input", "form"):
            inputs.append("user_input")
        if comp_type in ("button",):
            outputs.append("action_trigger")
        if comp_type in ("list", "table", "chart"):
            outputs.append("data_display")
            inputs.append("data_source")

        features.append({
            "name": comp_label or f"{page_name}_{comp_type}",
            "description": description,
            "page": page_name,
            "type": comp_type,
            "inputs": inputs,
            "outputs": outputs
        })

    # Also capture interactions as features
    for interaction in page.get("interactions", []):
        trigger = interaction.get("trigger", "")
        action = interaction.get("action", "")
        if trigger and action:
            features.append({
                "name": f"{trigger} → {action}",
                "description": f"Interaction: when {trigger}, then {action}",
                "page": page_name,
                "type": "interaction",
                "inputs": [trigger],
                "outputs": [action]
            })

print(f"[3/6] Extracted {len(features)} features from mock_ui.json")

with open(HERE / "features.json", "w", encoding="utf-8") as f:
    json.dump({"features": features}, f, separators=(',', ':'))

print(f"[3/6] Done → features.json")
