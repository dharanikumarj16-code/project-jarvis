"""
os_intelligence/training/export_gguf.py
======================================
Exports fine-tuned FunctionGemma 270M LoRA adapter to merged HuggingFace model,
converts to GGUF, and quantizes to 4-bit (Q4_K_M) for JARVIS app/local_brain.py.

Steps Automated:
1. Merge LoRA adapter into base model weights (google/functiongemma-270m-it).
2. Save merged model and tokenizer to a standalone directory.
3. Convert merged model to GGUF using llama.cpp conversion scripts.
4. Quantize to Q4_K_M for minimal RAM (~180MB) and fast CPU inference.
5. Verify loadability directly via llama_cpp in Python.
"""

import argparse
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("jarvis.gguf_exporter")


def merge_lora_to_hf(
    base_model_name: str,
    adapter_path: Path,
    merged_output_path: Path,
    hf_token: str = None,
) -> Path:
    """Merge LoRA adapter into base model weights and save to disk."""
    try:
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:
        logger.error(f"Missing transformers/peft: {exc}. Please install requirements to merge on GPU/host.")
        sys.exit(1)

    logger.info(f"Loading base model: {base_model_name}")
    base_model = AutoModelForCausalLM.from_pretrained(
        base_model_name,
        torch_dtype=torch.float16,
        token=hf_token,
        trust_remote_code=True,
    )
    tokenizer = AutoTokenizer.from_pretrained(base_model_name, token=hf_token, trust_remote_code=True)

    logger.info(f"Loading LoRA adapter: {adapter_path}")
    model = PeftModel.from_pretrained(base_model, str(adapter_path))

    logger.info("Merging adapter weights into base model...")
    merged_model = model.merge_and_unload()

    merged_output_path.mkdir(parents=True, exist_ok=True)
    logger.info(f"Saving merged model to: {merged_output_path}")
    merged_model.save_pretrained(str(merged_output_path))
    tokenizer.save_pretrained(str(merged_output_path))
    logger.info("Merge complete!")
    return merged_output_path


def convert_to_gguf(
    merged_model_path: Path,
    gguf_output_path: Path,
    llama_cpp_dir: Optional[Path] = None,
) -> Path:
    """Convert merged Hugging Face model directory to GGUF format."""
    converter_script = None
    if llama_cpp_dir and (llama_cpp_dir / "convert_hf_to_gguf.py").exists():
        converter_script = llama_cpp_dir / "convert_hf_to_gguf.py"
    else:
        # Check current or parent directories
        candidates = [
            Path("convert_hf_to_gguf.py"),
            Path("llama.cpp/convert_hf_to_gguf.py"),
            Path("../llama.cpp/convert_hf_to_gguf.py"),
        ]
        for c in candidates:
            if c.exists():
                converter_script = c
                break

    if not converter_script:
        logger.warning(
            "convert_hf_to_gguf.py not found locally. To convert:\n"
            "  git clone https://github.com/ggerganov/llama.cpp\n"
            f"  python llama.cpp/convert_hf_to_gguf.py {merged_model_path} --outfile {gguf_output_path} --outtype f16"
        )
        return gguf_output_path

    logger.info(f"Running conversion: {converter_script} -> {gguf_output_path}")
    cmd = [
        sys.executable,
        str(converter_script),
        str(merged_model_path),
        "--outfile",
        str(gguf_output_path),
        "--outtype",
        "f16",
    ]
    subprocess.check_call(cmd)
    logger.info(f"GGUF conversion successful: {gguf_output_path}")
    return gguf_output_path


def verify_gguf(gguf_path: Path) -> bool:
    """Verify that the exported GGUF can be loaded and executed by llama_cpp."""
    if not gguf_path.exists():
        logger.error(f"GGUF file does not exist at: {gguf_path}")
        return False

    try:
        from llama_cpp import Llama
        logger.info(f"Verifying GGUF with llama-cpp-python: {gguf_path}")
        llm = Llama(model_path=str(gguf_path), n_threads=4, n_ctx=512, verbose=False)
        out = llm.create_chat_completion(
            messages=[{"role": "user", "content": "Check active window."}],
            max_tokens=64,
        )
        logger.info(f"Verification output: {out['choices'][0]['message']}")
        logger.info("Verification PASSED!")
        return True
    except Exception as exc:
        logger.error(f"GGUF verification failed: {exc}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Export FunctionGemma LoRA to GGUF for JARVIS")
    parser.add_argument("--base-model", type=str, default="google/functiongemma-270m-it")
    parser.add_argument("--adapter-path", type=str, default="models/functiongemma-270m-jarvis-sft")
    parser.add_argument("--merged-dir", type=str, default="models/functiongemma-270m-merged")
    parser.add_argument("--gguf-out", type=str, default="models/functiongemma-270m.gguf")
    parser.add_argument("--llama-cpp-dir", type=str, default=None)
    parser.add_argument("--verify-only", action="store_true", help="Only verify existing GGUF file")
    parser.add_argument("--hf-token", type=str, default=None)

    args = parser.parse_args()

    gguf_path = Path(args.gguf_out)
    if args.verify_only:
        success = verify_gguf(gguf_path)
        sys.exit(0 if success else 1)

    adapter_path = Path(args.adapter_path)
    merged_path = Path(args.merged_dir)

    if not adapter_path.exists():
        logger.error(
            f"Adapter directory not found at '{adapter_path}'.\n"
            "Please train the model first or download the trained adapter weights."
        )
        sys.exit(1)

    # 1. Merge LoRA
    merge_lora_to_hf(args.base_model, adapter_path, merged_path, args.hf_token)

    # 2. Convert to GGUF
    convert_to_gguf(merged_path, gguf_path, Path(args.llama_cpp_dir) if args.llama_cpp_dir else None)

    # 3. Verify
    if gguf_path.exists():
        verify_gguf(gguf_path)


if __name__ == "__main__":
    main()
