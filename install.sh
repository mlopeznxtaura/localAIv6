#!/usr/bin/env bash
# =============================================================================
# local-ai-v6 — One-Shot WSL2 Install Script
# Machine-executable. Idempotent. Run from any directory.
#
# Environment: WSL2 / Ubuntu 24.04, RTX 5090, 128GB RAM, Ryzen 9 7950X
# Ollama endpoint: http://172.30.80.1:11434
# Model: gemma4:26b
#
# Usage:
#   chmod +x install.sh && ./install.sh
#
# What this does:
#   1. Installs system deps (at, jq, curl, git, nodejs, npm)
#   2. Installs Python deps (pipeline + training/export)
#   3. Pulls gemma4:26b via Ollama
#   4. Installs Node deps for API and UI
#   5. Runs pre-flight check
#   6. Prints usage
# =============================================================================

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIPELINE_DIR="$REPO_DIR/pipeline"
API_DIR="$REPO_DIR/api"
UI_DIR="$REPO_DIR/ui"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║         local-ai-v6 — Install            ║"
echo "║  Stateless Generation + Learning         ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "Repo: $REPO_DIR"
echo ""

# ── 1. System deps ────────────────────────────────────────────────────────────
echo "▶ System dependencies..."
sudo apt-get update -qq
sudo apt-get install -y -qq at jq curl git python3 python3-pip nodejs npm
sudo service atd start || true
echo "  ✓ at, jq, curl, git, python3, nodejs, npm"

# ── 2. Python pipeline deps ───────────────────────────────────────────────────
echo ""
echo "▶ Python pipeline dependencies..."
pip3 install --quiet --break-system-packages \
    requests \
    beautifulsoup4
echo "  ✓ requests, beautifulsoup4"

# ── 3. Python training/export deps ───────────────────────────────────────────
echo ""
echo "▶ Python training/export dependencies..."
echo "  (torch is large — this may take several minutes)"
pip3 install --quiet --break-system-packages \
    torch \
    transformers \
    peft \
    bitsandbytes \
    accelerate
echo "  ✓ torch, transformers, peft, bitsandbytes, accelerate"

# ── 4. Ollama model ───────────────────────────────────────────────────────────
echo ""
echo "▶ Checking Ollama + gemma4:26b..."
if ! curl -sf http://172.30.80.1:11434/api/tags > /dev/null 2>&1; then
    echo "  ⚠ Ollama not reachable at http://172.30.80.1:11434"
    echo "  Make sure 'ollama serve' is running in WSL before the pipeline."
    echo "  Skipping model pull — run manually: ollama pull gemma4:26b"
else
    MODELS=$(curl -sf http://172.30.80.1:11434/api/tags | python3 -c "import sys,json; print(' '.join(m['name'] for m in json.load(sys.stdin).get('models',[])))")
    if echo "$MODELS" | grep -q "gemma4"; then
        echo "  ✓ gemma4 already pulled: $(echo $MODELS | grep -o 'gemma4[^ ]*' | head -1)"
    else
        echo "  Pulling gemma4:26b (~18GB — this will take a while)..."
        ollama pull gemma4:26b
        echo "  ✓ gemma4:26b pulled"
    fi
    # Auto-patch MODEL in ollama_client.py
    BEST=$(curl -sf http://172.30.80.1:11434/api/tags | python3 -c "
import sys, json
models = [m['name'] for m in json.load(sys.stdin).get('models', []) if 'gemma4' in m['name']]
print(models[0] if models else 'gemma4:26b')
")
    sed -i "s/MODEL = \".*\"/MODEL = \"$BEST\"/" "$PIPELINE_DIR/ollama_client.py"
    echo "  ✓ ollama_client.py patched: MODEL = \"$BEST\""
fi

# ── 5. Node deps ──────────────────────────────────────────────────────────────
echo ""
echo "▶ Node dependencies (API)..."
cd "$API_DIR" && npm install --silent
echo "  ✓ API deps installed"

echo ""
echo "▶ Node dependencies (UI)..."
cd "$UI_DIR" && npm install --silent
echo "  ✓ UI deps installed"

# ── 6. Directory structure ────────────────────────────────────────────────────
cd "$REPO_DIR"
mkdir -p training_data/raw student_model exports output tool_cache
echo ""
echo "  ✓ Directory structure ready"

# ── 7. Pre-flight ─────────────────────────────────────────────────────────────
echo ""
echo "▶ Running pre-flight check..."
cd "$PIPELINE_DIR"
python3 check.py || true

# ── 8. Done ───────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║           Installation Complete          ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "  Run the pipeline:"
echo "    cd $PIPELINE_DIR"
echo '    python3 run.py "describe what you want to build"'
echo ""
echo "  Start API + UI (two terminals):"
echo "    cd $API_DIR && npm start          # API on :3000"
echo "    cd $UI_DIR  && npm start          # UI  on :3001 (dev)"
echo ""
echo "  Monitor:"
echo "    python3 $REPO_DIR/scripts/status.py --watch"
echo ""
echo "  Accelerate a task:"
echo "    python3 $REPO_DIR/scripts/accelerate.py T001"
echo ""
echo "  Training stats:"
echo "    python3 $PIPELINE_DIR/trainer.py --status"
echo ""
echo "  Export student model:"
echo "    python3 $PIPELINE_DIR/export.py --format huggingface"
echo "    python3 $PIPELINE_DIR/export.py --format ollama --model-name local-ai-student"
echo ""
echo "  Architecture diagram: $REPO_DIR/architecture.png"
echo ""
