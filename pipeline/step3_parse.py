"""
local-ai-v6 — Step 3: Feature Parsing
Reads:  mock_ui.html
Writes: features.json
BeautifulSoup first — zero tokens on what the parser handles.
"""
import json
from pathlib import Path
from bs4 import BeautifulSoup
from ollama_client import ask, check_model, safe_json

check_model()
HERE = Path(__file__).parent

with open(HERE / "mock_ui.html", "r", encoding="utf-8") as f:
    html = f.read()

soup = BeautifulSoup(html, "html.parser")
elements = []
for btn in soup.find_all("button"):
    t = btn.get_text(strip=True)
    if t:
        elements.append({"type": "button", "label": t})
for inp in soup.find_all("input"):
    label = inp.get("placeholder") or inp.get("name") or inp.get("type", "input")
    elements.append({"type": "input", "label": label})
for form in soup.find_all("form"):
    elements.append({"type": "form", "label": form.get("id") or "form"})
for h in soup.find_all(["h1", "h2", "h3"]):
    t = h.get_text(strip=True)
    if t:
        elements.append({"type": "section", "label": t})

print(f"[3/6] Parsed {len(elements)} elements. Extracting features...")

compact = json.dumps(elements, separators=(',', ':'))
user = (
    "Given this UI element list, return a JSON array of app features. "
    "Each: {\"name\":\"...\",\"description\":\"...\",\"inputs\":[],\"outputs\":[]}. "
    "Return ONLY valid minified JSON array.\n\n" + compact
)
raw_out, fb = ask(3, "feature_parsing", "extract", user, budget=1024, call_index=0)
features = safe_json(raw_out, None)
if not isinstance(features, list) or not features:
    features = [{"name": e["label"], "description": e["type"], "inputs": [], "outputs": []} for e in elements]

output = {"parsed_elements": elements, "features": features}
with open(HERE / "features.json", "w", encoding="utf-8") as f:
    json.dump(output, f, separators=(',', ':'))

print(f"[3/6] Done → features.json ({len(features)} features)")
