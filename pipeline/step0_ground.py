"""
local-ai-v6 — Step 0: Web Grounding
Reads:  user_prompt.txt
Writes: grounded_context.json
"""
import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from ollama_client import ask, check_model, safe_json, cache_get, cache_set

check_model()
HERE = Path(__file__).parent

with open(HERE / "user_prompt.txt", "r", encoding="utf-8") as f:
    raw = f.read().strip()

print("[0/6] Web grounding...")

# Phase A: extract search queries
user_a = (
    "Extract 2-3 web search queries to ground this build intent in current best practices. "
    "Return ONLY a JSON array of strings.\n\nIntent: " + raw
)
raw_a, fb_a = ask(0, "web_grounding", "query_extraction", user_a, budget=128, call_index=0)
queries = safe_json(raw_a, None)
if not isinstance(queries, list) or not queries:
    queries = [raw.split()[:8] and " ".join(raw.split()[:8]) + " best practices 2026"]
queries = queries[:3]
print(f"[0/6] Queries: {queries}")

# Phase B: DuckDuckGo (tool cache first)
search_results = []
for q in queries:
    cache_data = {"tool": "duckduckgo", "query": q}
    cached = cache_get(cache_data)
    if cached:
        search_results.append(cached)
        print(f"[0/6] cache hit: {q[:40]}")
        continue
    try:
        encoded = urllib.parse.quote_plus(q)
        url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1&skip_disambig=1"
        req = urllib.request.Request(url, headers={"User-Agent": "local-ai-v6/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        abstract = data.get("AbstractText", "")
        related = [r.get("Text", "") for r in data.get("RelatedTopics", [])[:3] if isinstance(r, dict)]
        result_text = abstract or " | ".join(filter(None, related)) or "no_results"
        result = {"query": q, "result": result_text[:600]}
        cache_set(cache_data, result)
        search_results.append(result)
        print(f"[0/6] ✓ {q[:40]}")
    except Exception as e:
        result = {"query": q, "result": "search_unavailable"}
        search_results.append(result)
        print(f"[0/6] ✗ {q[:40]} ({e})")

# Phase C: synthesize
user_c = (
    "Synthesize these search results with the build intent. "
    "Return ONLY minified JSON: "
    "{\"grounded_intent\":\"...\",\"current_stack\":[],\"patterns\":[],\"gotchas\":[],\"search_confidence\":\"high|medium|low\"}\n\n"
    f"Intent: {raw}\nSearch: {json.dumps(search_results, separators=(',',':'))}"
)
raw_c, fb_c = ask(0, "web_grounding", "synthesis", user_c, budget=512, call_index=1)
grounded = safe_json(raw_c, {
    "grounded_intent": raw,
    "current_stack": [],
    "patterns": [],
    "gotchas": [],
    "search_confidence": "low"
})

output = {
    "raw_intent": raw,
    "search_results": search_results,
    "grounded": grounded,
    "grounded_at": datetime.utcnow().isoformat() + "Z"
}

with open(HERE / "grounded_context.json", "w", encoding="utf-8") as f:
    json.dump(output, f, separators=(',', ':'))

print(f"[0/6] Done → grounded_context.json confidence={grounded.get('search_confidence','?')}")
