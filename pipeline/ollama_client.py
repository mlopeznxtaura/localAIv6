"""
local-ai-v6 — ollama_client.py
Shared by all pipeline steps. Every LLM call writes immediately to stream.jsonl.
No StepCollector. No buffering. No pruning at write time.
Trainer filters used_fallback at read time.
"""
import json
import re
import time
import hashlib
import os
import requests
from datetime import datetime, timezone
from pathlib import Path

OLLAMA_HOST = "http://localhost:11434"
MODEL = "gemma4:26b-optimized"  # auto-patched by check.py

BASE = Path(__file__).parent.parent
TRAINING_DIR = BASE / "training_data"
RAW_DIR = TRAINING_DIR / "raw"
STREAM_FILE = TRAINING_DIR / "stream.jsonl"
TOOL_CACHE_DIR = BASE / "tool_cache"

for d in [TRAINING_DIR, RAW_DIR, TOOL_CACHE_DIR]:
    d.mkdir(exist_ok=True)

SESSION_ID = os.environ.get("LAV6_SESSION_ID", datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))

STATELESS_SYSTEM = (
    "JSON ONLY. Stateless. No prose. No markdown. "
    "Compress next_input >=40%. Stay under token budget. "
    "Use web_search/fetch_url if knowledge may be outdated (cutoff before 2025-04-01). "
    "If input malformed: {\"error\":\"malformed_input\"}"
)


# ── Tool cache ────────────────────────────────────────────────────────────────

def _cache_key(data: dict) -> str:
    return hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()

def cache_get(data: dict):
    k = _cache_key(data)
    f = TOOL_CACHE_DIR / f"{k}.json"
    return json.loads(f.read_text()) if f.exists() else None

def cache_set(data: dict, result):
    k = _cache_key(data)
    (TOOL_CACHE_DIR / f"{k}.json").write_text(json.dumps(result))


# ── JSON cleaning ─────────────────────────────────────────────────────────────

def strip_fences(text: str) -> str:
    t = text.strip()
    t = re.sub(r'^```[a-z]*\n?', '', t)
    t = re.sub(r'\n?```$', '', t)
    return t.strip()

def safe_json(raw: str, fallback=None):
    try:
        return json.loads(strip_fences(raw))
    except (json.JSONDecodeError, ValueError):
        return fallback


# ── Per-call training write ───────────────────────────────────────────────────

def _write_training(record: dict):
    """Append one record immediately. Never buffered. Never gated."""
    with open(STREAM_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    # Also write individual file for inspection
    session_dir = RAW_DIR / SESSION_ID
    session_dir.mkdir(exist_ok=True)
    fname = f"step{record['step']}_{record['step_name']}_{record['substep']}_{record['call_index']}.json"
    (session_dir / fname).write_text(json.dumps(record, indent=2))


# ── Core ask ─────────────────────────────────────────────────────────────────

def ask(
    step: int,
    step_name: str,
    substep: str,
    user_content: str,
    budget: int = 1024,
    call_index: int = 0,
    require_tools: bool = False
) -> tuple:
    """
    Make one stateless Ollama call.
    Returns (raw_response: str, used_fallback: bool)
    Writes training record immediately regardless of outcome.
    """
    system = STATELESS_SYSTEM
    if require_tools:
        system += " Prefer cached web results when available."

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps({
                "step": step,
                "step_name": step_name,
                "substep": substep,
                "input": user_content,
                "budget_tokens": budget
            })}
        ],
        "stream": False,
        "options": {
            "num_predict": budget,
            "temperature": 0.15
        }
    }

    start = time.time()
    try:
        r = requests.post(f"{OLLAMA_HOST}/api/chat", json=payload, timeout=600)
        r.raise_for_status()
        raw = r.json()["message"]["content"]
    except requests.exceptions.ConnectionError:
        raise SystemExit(
            f"\n[local-ai-v6] Cannot reach Ollama at {OLLAMA_HOST}\n"
            f"  Fix: ollama serve\n"
        )
    except Exception as e:
        raise SystemExit(f"\n[local-ai-v6] Ollama error: {e}\n")

    latency_ms = int((time.time() - start) * 1000)
    parsed = safe_json(raw)
    used_fallback = parsed is None or (isinstance(parsed, dict) and "error" in parsed)

    record = {
        # Generic instruction-following fields (Alpaca compatible)
        "instruction": f"Step {step} ({step_name}) substep {substep}: {user_content[:500]}",
        "input": "",
        "output": raw,
        # Metadata
        "metadata": {
            "session_id": SESSION_ID,
            "step": step,
            "step_name": step_name,
            "substep": substep,
            "call_index": call_index,
            "system_prompt": system,
            "user_content": user_content,
            "raw_response": raw,
            "parsed_ok": not used_fallback,
            "used_fallback": used_fallback,
            "latency_ms": latency_ms,
            "budget_tokens": budget,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    }
    _write_training(record)

    return raw, used_fallback


def check_model():
    try:
        r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=10)
        r.raise_for_status()
        names = [m["name"] for m in r.json().get("models", [])]
        if not any("gemma4" in n for n in names):
            print(f"[local-ai-v6] WARNING: gemma4 not found. Available: {names}")
            print(f"  Run: ollama pull gemma4:26b")
    except Exception as e:
        raise SystemExit(f"\n[local-ai-v6] Ollama unreachable: {e}\n")
