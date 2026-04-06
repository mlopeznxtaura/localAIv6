"""
local-ai-v6 — check.py
Run first: python3 check.py
"""
import requests
import subprocess
import sys
import re
from pathlib import Path

OLLAMA_HOST = "http://172.30.80.1:11434"
HERE = Path(__file__).parent

print("local-ai-v6 — Pre-flight Check")
print("=" * 40)

# 1. Ollama
try:
    r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=8)
    r.raise_for_status()
    print(f"✓ Ollama reachable at {OLLAMA_HOST}")
except Exception as e:
    print(f"✗ Ollama unreachable: {e}")
    print(f"  Fix: ollama serve")
    sys.exit(1)

# 2. gemma4 — auto-patch
models = r.json().get("models", [])
names = [m["name"] for m in models]
matched = [n for n in names if "gemma4" in n]
if matched:
    best = matched[0]
    print(f"✓ Model: {best}")
    client = HERE / "ollama_client.py"
    src = client.read_text()
    patched = re.sub(r'MODEL = ".*?"', f'MODEL = "{best}"', src)
    client.write_text(patched)
    print(f"  ✓ ollama_client.py patched → MODEL = \"{best}\"")
else:
    print(f"✗ gemma4 not found. Available: {names}")
    print(f"  Fix: ollama pull gemma4:26b")
    sys.exit(1)

# 3. Pipeline Python deps
pipeline_deps = [("requests", "requests"), ("beautifulsoup4", "bs4")]
missing = []
for pkg, imp in pipeline_deps:
    try:
        __import__(imp)
        print(f"✓ {pkg}")
    except ImportError:
        missing.append(pkg)
if missing:
    print(f"✗ Missing: {missing}")
    print(f"  Fix: pip3 install {' '.join(missing)} --break-system-packages")
    sys.exit(1)

# 4. Training/export deps (warn only — heavy, pipeline runs without them)
heavy_deps = ["torch", "transformers", "peft", "bitsandbytes", "accelerate"]
heavy_missing = []
for pkg in heavy_deps:
    try:
        __import__(pkg)
        print(f"✓ {pkg}")
    except ImportError:
        heavy_missing.append(pkg)
if heavy_missing:
    print(f"⚠ Training deps not installed: {heavy_missing}")
    print(f"  Pipeline runs fine. For trainer.py + export.py:")
    print(f"  pip3 install {' '.join(heavy_missing)} --break-system-packages")
else:
    print(f"✓ All training deps present")

# 5. `at` daemon
try:
    result = subprocess.run(["which", "at"], capture_output=True, text=True)
    if result.returncode == 0:
        print(f"✓ `at` available at {result.stdout.strip()}")
        # Ensure atd is running
        subprocess.run(["sudo", "service", "atd", "start"],
                       capture_output=True, timeout=5)
        print(f"  ✓ atd service started")
    else:
        print(f"⚠ `at` not found — install: sudo apt install at")
        print(f"  Fallback: sleep-based scheduling will be used")
except Exception as e:
    print(f"⚠ `at` check failed: {e} — sleep fallback will be used")

# 6. Web grounding
try:
    import urllib.request
    urllib.request.urlopen("https://api.duckduckgo.com", timeout=5)
    print(f"✓ Web search reachable (DuckDuckGo)")
except Exception:
    print(f"⚠ Web search offline — Step 0 uses search_confidence: low")

print()
print("Ready.")
print()
print("Run pipeline:")
print('  python3 run.py "describe what you want to build"')
print()
print("Monitor:")
print("  python3 scripts/status.py")
print()
print("Accelerate task:")
print("  python3 scripts/accelerate.py T001")
print()
print("Training stats:")
print("  python3 trainer.py --status")
print()
print("Export student:")
print("  python3 export.py --format huggingface")
print()
