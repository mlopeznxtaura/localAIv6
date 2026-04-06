"""
local-ai-v6 — Step 1: Prompt Compression
Reads:  grounded_context.json
Writes: compressed_intent.txt
"""
import json
import os
from pathlib import Path
from ollama_client import ask, check_model, safe_json

check_model()
HERE = Path(__file__).parent

with open(HERE / "grounded_context.json", "r", encoding="utf-8") as f:
    ctx = json.load(f)

raw = ctx.get("raw_intent", "")
grounded = ctx.get("grounded", {})
stack = grounded.get("current_stack", [])
grounded_intent = grounded.get("grounded_intent", raw)

# Compression aggressiveness: 0 = preserve everything, 50 = maximum compression
# Set via COMPRESSION_AGGRESSIVENESS env var (0-50). Default 20.
aggressiveness = max(0, min(50, int(os.environ.get("COMPRESSION_AGGRESSIVENESS", "20"))))

if aggressiveness == 0:
    compression_instruction = (
        "Preserve the user's intent exactly as written. "
        "Clean up grammar and punctuation only. Do not remove any details. "
        "Return as one sentence."
    )
elif aggressiveness <= 15:
    compression_instruction = (
        "Lightly compress this intent. Keep all specific details, tech choices, and constraints. "
        "Remove only filler words. Return as one clean sentence."
    )
elif aggressiveness <= 30:
    compression_instruction = (
        "Compress this intent moderately. Keep core features and key technical details. "
        "Remove redundancy and filler. Return as one clean sentence."
    )
elif aggressiveness <= 40:
    compression_instruction = (
        "Compress this intent aggressively. Keep only the essential goal and primary constraints. "
        "Drop secondary details. Return as one clean sentence."
    )
else:
    compression_instruction = (
        "Compress this intent to maximum brevity. Core goal only — one tight sentence. "
        "Strip everything non-essential."
    )

print(f"[1/6] Compressing intent (aggressiveness={aggressiveness}%)...")

user = (
    f"{compression_instruction} Same language as input. No quotes, no punctuation wrapping.\n\n"
    f"Raw: {raw}\nGrounded: {grounded_intent}\nStack: {', '.join(stack) if stack else 'any'}"
)
raw_out, fb = ask(1, "prompt_compression", "compress", user, budget=128, call_index=0)
result = raw_out.strip().strip('"').strip("'").strip()
if not result or len(result) < 5:
    result = grounded_intent or raw

with open(HERE / "compressed_intent.txt", "w", encoding="utf-8") as f:
    f.write(result)

print(f"[1/6] Done → {result}")
