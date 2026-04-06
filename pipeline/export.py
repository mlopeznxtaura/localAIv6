"""
local-ai-v6 — export.py
Export trained student model (LoRA adapters) to deployment format.
Usage:
  python3 export.py --format huggingface
  python3 export.py --format llamacpp --llama-cpp-dir ~/llama.cpp
  python3 export.py --format ollama --model-name local-ai-student
  python3 export.py --format vllm
  python3 export.py --status
"""
import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
STUDENT_DIR = PROJECT_ROOT / "student_model"
EXPORTS_DIR = PROJECT_ROOT / "exports"
STUDENT_BASE = "google/gemma-2-9b-it"


def check_adapters():
    if not (STUDENT_DIR / "adapter_config.json").exists():
        print(f"[export] No trained adapters at {STUDENT_DIR}")
        print(f"  Run: python3 trainer.py --status")
        sys.exit(1)


def merge_to_hf(out_path: Path):
    print(f"[export] Merging LoRA into base model...")
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from peft import PeftModel
    except ImportError as e:
        print(f"[export] Missing: {e}")
        print(f"  pip3 install transformers peft torch --break-system-packages")
        sys.exit(1)
    tokenizer = AutoTokenizer.from_pretrained(STUDENT_BASE)
    model = AutoModelForCausalLM.from_pretrained(STUDENT_BASE, device_map="cpu", torch_dtype="auto")
    model = PeftModel.from_pretrained(model, str(STUDENT_DIR))
    merged = model.merge_and_unload()
    out_path.mkdir(parents=True, exist_ok=True)
    merged.save_pretrained(str(out_path))
    tokenizer.save_pretrained(str(out_path))
    print(f"[export] HuggingFace model → {out_path}")
    return out_path


def export_huggingface():
    out = EXPORTS_DIR / "huggingface"
    merge_to_hf(out)
    print(f"\nLoad with:")
    print(f"  from transformers import AutoModelForCausalLM")
    print(f"  model = AutoModelForCausalLM.from_pretrained('{out}')")


def export_vllm():
    out = EXPORTS_DIR / "huggingface"
    if not out.exists():
        merge_to_hf(out)
    print(f"\nvLLM: vllm serve {out} --dtype float16")


def export_llamacpp(llama_cpp_dir: str):
    hf_path = EXPORTS_DIR / "huggingface"
    if not hf_path.exists():
        merge_to_hf(hf_path)
    gguf_path = EXPORTS_DIR / "model.gguf"
    convert = Path(llama_cpp_dir) / "convert_hf_to_gguf.py"
    if not convert.exists():
        convert = Path(llama_cpp_dir) / "convert.py"
    if not convert.exists():
        print(f"[export] convert script not found in {llama_cpp_dir}")
        print(f"  git clone https://github.com/ggerganov/llama.cpp")
        print(f"  python3 {llama_cpp_dir}/convert_hf_to_gguf.py {hf_path} --outfile {gguf_path}")
        return
    result = subprocess.run([sys.executable, str(convert), str(hf_path), "--outfile", str(gguf_path)])
    if result.returncode == 0:
        print(f"[export] GGUF → {gguf_path}")
    else:
        print(f"[export] Conversion failed. Run manually above.")


def export_ollama(model_name: str, llama_cpp_dir: str):
    gguf_path = EXPORTS_DIR / "model.gguf"
    if not gguf_path.exists():
        export_llamacpp(llama_cpp_dir)
    if not gguf_path.exists():
        return
    modelfile = EXPORTS_DIR / "Modelfile"
    modelfile.write_text(
        f'FROM {gguf_path}\n'
        f'TEMPLATE """{{{{ .System }}}} {{{{ .Prompt }}}}"""\n'
        f'SYSTEM """JSON ONLY. Stateless. No prose. No markdown."""\n'
        f'PARAMETER temperature 0.15\n'
        f'PARAMETER num_predict 1024\n'
    )
    result = subprocess.run(["ollama", "create", model_name, "-f", str(modelfile)])
    if result.returncode == 0:
        print(f"[export] ✓ ollama run {model_name}")
    else:
        print(f"[export] ollama create failed. Run: ollama create {model_name} -f {modelfile}")


def show_status():
    print(f"\n[export] Student model status:")
    print(f"  Adapters: {(STUDENT_DIR / 'adapter_config.json').exists()}")
    for fmt in ["huggingface", "model.gguf"]:
        p = EXPORTS_DIR / fmt
        print(f"  Export '{fmt}': {'exists' if p.exists() else 'not exported'}")
    print()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", choices=["huggingface", "vllm", "llamacpp", "ollama"])
    parser.add_argument("--llama-cpp-dir", default="~/llama.cpp")
    parser.add_argument("--model-name", default="local-ai-student")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()
    EXPORTS_DIR.mkdir(exist_ok=True)
    if args.status:
        show_status()
        return
    if not args.format:
        parser.print_help()
        return
    check_adapters()
    llama_dir = str(Path(args.llama_cpp_dir).expanduser())
    if args.format == "huggingface":
        export_huggingface()
    elif args.format == "vllm":
        export_vllm()
    elif args.format == "llamacpp":
        export_llamacpp(llama_dir)
    elif args.format == "ollama":
        export_ollama(args.model_name, llama_dir)


if __name__ == "__main__":
    main()
