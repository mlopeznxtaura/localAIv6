"""
local-ai-v6 — trainer.py
Offline student fine-tuning. Run manually. Completely separate from pipeline.
Reads training_data/stream.jsonl — filters used_fallback at read time.
Trains on both generation examples AND task completion records (est vs actual).

Usage:
  python3 trainer.py --status
  python3 trainer.py --min-examples 20 --epochs 1
"""
import argparse
import json
from pathlib import Path
from collections import Counter

PROJECT_ROOT = Path(__file__).parent
STREAM_FILE = PROJECT_ROOT / "training_data" / "stream.jsonl"
STUDENT_DIR = PROJECT_ROOT / "student_model"
STUDENT_BASE = "google/gemma-2-9b-it"

LORA_CONFIG = {
    "r": 16,
    "lora_alpha": 32,
    "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj"],
    "lora_dropout": 0.05,
    "bias": "none",
    "task_type": "CAUSAL_LM"
}
TRAIN_CONFIG = {
    "learning_rate": 5e-4,
    "grad_clip": 1.0,
    "max_seq_length": 1024,
    "batch_size": 1,
    "gradient_accumulation": 4
}


def load_clean_examples(min_examples: int = 1):
    if not STREAM_FILE.exists():
        print(f"[trainer] No stream.jsonl yet.")
        return []
    examples = []
    with open(STREAM_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ex = json.loads(line)
                meta = ex.get("metadata", {})
                # Filter: only clean calls
                if not meta.get("used_fallback", True):
                    examples.append(ex)
            except json.JSONDecodeError:
                continue
    print(f"[trainer] {len(examples)} clean examples from stream.jsonl")
    if len(examples) < min_examples:
        print(f"[trainer] Need {min_examples}+ examples. Run more pipeline builds first.")
        return []
    return examples


def show_status():
    if not STREAM_FILE.exists():
        print("[trainer] No training data yet.")
        return
    all_lines, clean, fallback, completions = 0, 0, 0, 0
    step_counts = Counter()
    with open(STREAM_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            all_lines += 1
            try:
                ex = json.loads(line)
                meta = ex.get("metadata", {})
                if meta.get("type") == "task_completion":
                    completions += 1
                if meta.get("used_fallback"):
                    fallback += 1
                else:
                    clean += 1
                    step_counts[meta.get("step_name", "unknown")] += 1
            except Exception:
                pass
    print(f"\n[trainer] Training data:")
    print(f"  Total records:       {all_lines}")
    print(f"  Clean (trainable):   {clean}")
    print(f"  Fallback (skipped):  {fallback}")
    print(f"  Task completions:    {completions}")
    print(f"  By step:")
    for step, count in sorted(step_counts.items()):
        print(f"    {step}: {count}")
    adapters = STUDENT_DIR / "adapter_config.json"
    print(f"  Adapters trained:    {adapters.exists()}")
    print()


def format_example(ex: dict, tokenizer):
    instruction = ex.get("instruction", "")
    output = ex.get("output", "")
    text = f"### Instruction:\n{instruction}\n\n### Response:\n{output}"
    tokenized = tokenizer(
        text, truncation=True, max_length=TRAIN_CONFIG["max_seq_length"],
        padding="max_length", return_tensors="pt"
    )
    tokenized["labels"] = tokenized["input_ids"].clone()
    return tokenized


def train(examples: list, epochs: int = 1):
    print(f"[trainer] Loading deps...")
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        from peft import LoraConfig, get_peft_model, PeftModel, prepare_model_for_kbit_training
    except ImportError as e:
        print(f"[trainer] Missing: {e}")
        print(f"  pip3 install transformers peft bitsandbytes accelerate torch --break-system-packages")
        return

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[trainer] Device: {device} | Examples: {len(examples)} | Epochs: {epochs}")

    bnb = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.float16
    )
    tokenizer = AutoTokenizer.from_pretrained(STUDENT_BASE)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        STUDENT_BASE, quantization_config=bnb, device_map="auto", torch_dtype=torch.float16
    )

    STUDENT_DIR.mkdir(exist_ok=True)
    if (STUDENT_DIR / "adapter_config.json").exists():
        print(f"[trainer] Loading existing adapters...")
        model = PeftModel.from_pretrained(model, str(STUDENT_DIR))
        model.train()
    else:
        print(f"[trainer] Creating new LoRA adapters...")
        # prepare_model_for_kbit_training MUST come before get_peft_model
        model = prepare_model_for_kbit_training(model)
        model = get_peft_model(model, LoraConfig(**LORA_CONFIG))

    model.print_trainable_parameters()
    optimizer = torch.optim.AdamW(model.parameters(), lr=TRAIN_CONFIG["learning_rate"])
    model.train()

    for epoch in range(epochs):
        epoch_loss = 0.0
        optimizer.zero_grad()
        for i, ex in enumerate(examples):
            batch = format_example(ex, tokenizer)
            ids = batch["input_ids"].to(device)
            mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)
            out = model(input_ids=ids, attention_mask=mask, labels=labels)
            loss = out.loss / TRAIN_CONFIG["gradient_accumulation"]
            loss.backward()
            epoch_loss += loss.item()
            if (i + 1) % TRAIN_CONFIG["gradient_accumulation"] == 0:
                torch.nn.utils.clip_grad_norm_(model.parameters(), TRAIN_CONFIG["grad_clip"])
                optimizer.step()
                optimizer.zero_grad()
            if (i + 1) % 10 == 0:
                print(f"  epoch {epoch+1} step {i+1}/{len(examples)} loss={epoch_loss/(i+1):.4f}")
        print(f"[trainer] Epoch {epoch+1} avg loss={epoch_loss/len(examples):.4f}")

    model.save_pretrained(str(STUDENT_DIR))
    tokenizer.save_pretrained(str(STUDENT_DIR))
    print(f"[trainer] Saved → {STUDENT_DIR}")
    print(f"[trainer] Export: python3 export.py --format huggingface")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-examples", type=int, default=10)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()
    if args.status:
        show_status()
        return
    examples = load_clean_examples(min_examples=args.min_examples)
    if examples:
        train(examples, epochs=args.epochs)


if __name__ == "__main__":
    main()
