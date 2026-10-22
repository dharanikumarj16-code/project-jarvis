"""
os_intelligence/training/train.py
================================
Supervised Fine-Tuning (SFT) script for JARVIS PC-Expert SLM (FunctionGemma 270M).

Key Capabilities:
- Full SFT training on Cloud / Colab GPUs using TRL & PEFT LoRA.
- Completion-only loss masking: computes loss exclusively on model tool calls and reasoning.
- CPU Smoke Test Mode: verifies model loading, gradient propagation, and tokenizer formatting.
- Offline Pipeline Validation Mode: verifies prompt assembly and data collation without GPU.
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("jarvis.sft_trainer")

DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "configs" / "training_config.yaml"


def format_sample_to_text(sample: Dict[str, Any]) -> str:
    """Format a multi-turn JARVIS training sample into FunctionGemma standard chat format.

    FunctionGemma format specification:
    <start_of_turn>user
    Available Tools:
    {tool_schemas}

    {user_message}<end_of_turn>
    <start_of_turn>model
    call:tool_name{arguments}<end_of_turn>
    <start_of_turn>tool
    {observation}<end_of_turn>
    <start_of_turn>model
    {response}<end_of_turn>
    """
    tools = sample.get("tools", [])
    messages = sample.get("messages", [])

    tools_str = json.dumps(tools, indent=2)
    formatted_parts: List[str] = []

    first_user = True
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content", "")

        if role == "user":
            if first_user:
                user_body = f"Available Tools:\n{tools_str}\n\nTask: {content}"
                formatted_parts.append(f"<start_of_turn>user\n{user_body}<end_of_turn>")
                first_user = False
            else:
                formatted_parts.append(f"<start_of_turn>user\n{content}<end_of_turn>")
        elif role in ["model", "assistant"]:
            formatted_parts.append(f"<start_of_turn>model\n{content}<end_of_turn>")
        elif role == "tool":
            formatted_parts.append(f"<start_of_turn>tool\n{content}<end_of_turn>")

    return "\n".join(formatted_parts)


def validate_pipeline_offline(config_dict: Dict[str, Any]) -> bool:
    """Validate data loading and formatting without requiring torch/transformers."""
    logger.info("=== Running Offline Pipeline Validation ===")
    train_path = Path(config_dict.get("data", {}).get("train_path", "os_intelligence/data/train.jsonl"))

    if not train_path.exists():
        logger.error(f"Training data not found at: {train_path}")
        return False

    with open(train_path, "r", encoding="utf-8") as f:
        samples = [json.loads(line) for line in f if line.strip()]

    logger.info(f"Loaded {len(samples)} samples from {train_path}")
    sample_text = format_sample_to_text(samples[0])
    logger.info(f"Sample 0 formatting preview (first 400 chars):\n{sample_text[:400]}...")

    # Verify critical FunctionGemma special tokens
    assert "<start_of_turn>user" in sample_text, "Missing user turn marker"
    assert "<start_of_turn>model" in sample_text, "Missing model turn marker"
    assert "<end_of_turn>" in sample_text, "Missing turn end marker"
    assert "Available Tools:" in sample_text, "Missing tool schemas injection"

    logger.info("Pipeline validation passed successfully!")
    return True


def run_training(args: argparse.Namespace, config_dict: Dict[str, Any]):
    """Execute SFT training loop with PEFT and TRL."""
    try:
        import torch
        from datasets import Dataset
        from peft import LoraConfig, get_peft_model, TaskType
        from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments
        from trl import DataCollatorForCompletionOnlyLM, SFTTrainer
    except ImportError as exc:
        logger.error(
            f"Training dependencies missing: {exc}.\n"
            "To train on GPU/Colab, please install: pip install torch transformers trl peft datasets accelerate pyyaml"
        )
        sys.exit(1)

    model_cfg = config_dict.get("model", {})
    peft_cfg = config_dict.get("peft", {})
    train_cfg = config_dict.get("training", {})
    loss_cfg = config_dict.get("loss_masking", {})
    data_cfg = config_dict.get("data", {})

    base_model_name = model_cfg.get("base_model_name_or_path", "google/functiongemma-270m-it")
    hf_token = args.hf_token or os.environ.get("HF_TOKEN") or None

    is_smoke_test = args.smoke_test
    device = "cpu" if (is_smoke_test or args.device == "cpu") else ("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Selected Device: {device} (Smoke test: {is_smoke_test})")

    # 1. Load Tokenizer
    logger.info(f"Loading Tokenizer: {base_model_name}")
    tokenizer = AutoTokenizer.from_pretrained(
        base_model_name,
        token=hf_token,
        trust_remote_code=True,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # 2. Load Dataset
    def load_jsonl_as_dataset(path_str: str) -> Dataset:
        p = Path(path_str)
        with open(p, "r", encoding="utf-8") as f:
            records = [json.loads(line) for line in f if line.strip()]
        texts = [format_sample_to_text(r) for r in records]
        return Dataset.from_dict({"text": texts})

    train_dataset = load_jsonl_as_dataset(data_cfg["train_path"])
    val_dataset = load_jsonl_as_dataset(data_cfg["val_path"])
    logger.info(f"Loaded Train: {len(train_dataset)} examples, Val: {len(val_dataset)} examples")

    # 3. Model Loading
    torch_dtype = torch.float32 if (device == "cpu" or is_smoke_test) else torch.bfloat16
    logger.info(f"Loading Model: {base_model_name} (dtype={torch_dtype})")
    model = AutoModelForCausalLM.from_pretrained(
        base_model_name,
        torch_dtype=torch_dtype,
        token=hf_token,
        trust_remote_code=True,
    )

    # 4. LoRA Adapter Configuration
    lora_config = LoraConfig(
        r=peft_cfg.get("r", 16),
        lora_alpha=peft_cfg.get("lora_alpha", 32),
        lora_dropout=peft_cfg.get("lora_dropout", 0.05),
        target_modules=peft_cfg.get("target_modules", ["q_proj", "v_proj", "k_proj", "o_proj"]),
        bias="none",
        task_type=TaskType.CAUSAL_LM,
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # 5. Completion-Only Data Collator
    # Essential for FunctionGemma: Only train on <start_of_turn>model completions!
    response_template = loss_cfg.get("response_template", "<start_of_turn>model\n")
    collator = DataCollatorForCompletionOnlyLM(
        response_template=response_template,
        tokenizer=tokenizer,
        mlm=False,
    )

    # 6. Training Arguments
    out_dir = args.output_dir or train_cfg.get("output_dir", "models/functiongemma-270m-jarvis-sft")
    if is_smoke_test:
        training_args = TrainingArguments(
            output_dir=out_dir,
            max_steps=5,
            per_device_train_batch_size=1,
            gradient_accumulation_steps=1,
            learning_rate=1e-4,
            logging_steps=1,
            save_strategy="no",
            use_cpu=True,
            report_to="none",
        )
    else:
        training_args = TrainingArguments(
            output_dir=out_dir,
            num_train_epochs=train_cfg.get("num_train_epochs", 3),
            per_device_train_batch_size=train_cfg.get("per_device_train_batch_size", 4),
            per_device_eval_batch_size=train_cfg.get("per_device_eval_batch_size", 4),
            gradient_accumulation_steps=train_cfg.get("gradient_accumulation_steps", 4),
            learning_rate=float(train_cfg.get("learning_rate", 2e-4)),
            lr_scheduler_type=train_cfg.get("lr_scheduler_type", "cosine"),
            warmup_ratio=float(train_cfg.get("warmup_ratio", 0.05)),
            weight_decay=float(train_cfg.get("weight_decay", 0.01)),
            logging_steps=train_cfg.get("logging_steps", 10),
            eval_strategy=train_cfg.get("eval_strategy", "steps"),
            eval_steps=train_cfg.get("eval_steps", 50),
            save_strategy=train_cfg.get("save_strategy", "steps"),
            save_steps=train_cfg.get("save_steps", 50),
            save_total_limit=train_cfg.get("save_total_limit", 2),
            bf16=(device == "cuda"),
            fp16=False,
            gradient_checkpointing=True,
            report_to="none",
        )

    # 7. Trainer Instantiation & Execution
    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        data_collator=collator,
        max_seq_length=model_cfg.get("max_seq_length", 2048),
        dataset_text_field="text",
    )

    logger.info("Starting training...")
    trainer.train()
    logger.info(f"Training completed. Saving fine-tuned adapter to {out_dir}")
    trainer.save_model(out_dir)
    tokenizer.save_pretrained(out_dir)
    logger.info("Model and tokenizer successfully saved!")


def main():
    parser = argparse.ArgumentParser(description="Train JARVIS PC-Expert SLM (FunctionGemma 270M)")
    parser.add_argument("--config", type=str, default=str(DEFAULT_CONFIG_PATH), help="Path to config YAML")
    parser.add_argument("--validate-pipeline", action="store_true", help="Validate data loading and formatting offline")
    parser.add_argument("--smoke-test", action="store_true", help="Run 5-step CPU smoke test")
    parser.add_argument("--device", type=str, choices=["cuda", "cpu"], default="cpu")
    parser.add_argument("--output-dir", type=str, default=None)
    parser.add_argument("--hf-token", type=str, default=None, help="Hugging Face access token")

    args = parser.parse_args()

    # Load configuration
    config_path = Path(args.config)
    if not config_path.exists():
        logger.error(f"Config file not found: {config_path}")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        config_dict = yaml.safe_load(f)

    if args.validate_pipeline:
        success = validate_pipeline_offline(config_dict)
        sys.exit(0 if success else 1)

    run_training(args, config_dict)


if __name__ == "__main__":
    main()
