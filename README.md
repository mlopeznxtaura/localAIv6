# local-ai-v6
## Stateless Generation + Deterministic Learning

See `architecture.png` for the full system diagram.

---

## One-Shot Install

```bash
chmod +x install.sh && ./install.sh
```

Installs all system deps, Python deps (including torch/transformers/peft),
pulls gemma4:26b, installs Node deps, patches model tag, runs pre-flight.
If deps already installed, pip/npm validate and move on.

---

## Architecture

```
user_prompt.txt
      ↓
step0_ground.py      → grounded_context.json   [live web + tool cache]
      ↓
step1_compress.py    → compressed_intent.txt   [configurable 0–50% aggressiveness]
      ↓
step2_mockui.py      → mock_ui.html
      ↓
step3_parse.py       → features.json           [BeautifulSoup first, zero tokens]
      ↓
step4_dag.py         → dag.json
      ↓
step5_tasks.py       → tasks.json + tests.json [per-task: spec→test→compile validate]
      ↓
step6_schedule.py    → cron_schedule.json      [CRON_FACTOR=10, floor=30s, no LLM]
      ↓
run.py fires `at` for root tasks only
      ↓
build_one.py         [per task: build→test→record actual→self-schedule dependents]
      ↓
output/ + output.zip [mandatory zip when all tasks complete]

training_data/stream.jsonl   ← every LLM call, written immediately, never gated
trainer.py                   ← offline, reads stream.jsonl, filters used_fallback at read time
export.py                    ← HuggingFace / vLLM / llama.cpp GGUF / Ollama Modelfile
```

**Self-scheduling loop:** `run.py` fires one `at` trigger per root task.
`build_one.py` fires `at` for dependents on completion using actual × CRON_FACTOR delay.
One initial trigger starts the entire chain. Python sets every subsequent alarm.

**Compression slider:** 0–50% aggressiveness set per-build via UI or
`COMPRESSION_AGGRESSIVENESS` env var. 0 = preserve exactly. 50 = maximum compression.
Every run's compression level is captured in training data for comparison.

**Estimation feedback loop:** Step 5 LLM estimates `est_seconds` per task.
`build_one.py` records `actual_seconds`. Delta written to `stream.jsonl`.
`trainer.py` trains student to predict actual from task description.
Running accuracy ratio dynamically adjusts remaining delays mid-run.

---

## Quick Start

```bash
# Pipeline only (headless)
cd pipeline
python3 run.py "an expense tracker with charts and CSV export"

# Monitor
python3 ../scripts/status.py --watch

# API + UI
cd ../api && npm start          # port 3000
cd ../ui  && npm start          # port 3001 (dev, proxies to 3000)
```

---

## Controls

```bash
# Accelerate a task (skip remaining delay)
python3 scripts/accelerate.py T001

# Training stats
python3 pipeline/trainer.py --status

# Train student (after enough examples)
python3 pipeline/trainer.py --min-examples 20 --epochs 1

# Export student
python3 pipeline/export.py --format huggingface
python3 pipeline/export.py --format ollama --model-name local-ai-student
python3 pipeline/export.py --format llamacpp --llama-cpp-dir ~/llama.cpp
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `LAV6_SESSION_ID` | timestamp | Set by run.py, shared across all steps |
| `CRON_FACTOR` | 10 | Delay multiplier (actual_seconds × factor) |
| `COMPRESSION_AGGRESSIVENESS` | 20 | 0=preserve, 50=maximum compression |
| `PORT` | 3000 | Express API port |

---

## File Layout

```
local-ai-v6/
├── install.sh              ← one-shot install
├── architecture.png        ← system diagram
├── pipeline/
│   ├── ollama_client.py    ← per-call training write, tool cache, stateless
│   ├── check.py
│   ├── run.py
│   ├── step0_ground.py
│   ├── step1_compress.py   ← compression aggressiveness slider
│   ├── step2_mockui.py
│   ├── step3_parse.py
│   ├── step4_dag.py
│   ├── step5_tasks.py
│   ├── step6_schedule.py
│   ├── build_one.py        ← self-scheduling, actual vs est, mandatory zip
│   ├── trainer.py
│   └── export.py
├── scripts/
│   ├── status.py
│   └── accelerate.py
├── api/
│   ├── server.js           ← Express, single port, serves React + API
│   └── package.json
├── ui/
│   ├── src/App.jsx         ← compression slider, task list, accelerate, download
│   ├── src/index.js
│   └── package.json
├── training_data/
│   ├── stream.jsonl        ← append-only, every LLM call
│   └── raw/<session>/      ← individual call dumps
├── student_model/          ← LoRA adapters (dormant until exported)
├── exports/                ← HF / GGUF / Ollama exports
├── tool_cache/             ← MD5-keyed web search cache
└── output/                 ← generated files + output.zip
```
