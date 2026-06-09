#!/usr/bin/env python3
"""LoRA fine-tuning script for Android prompt-to-plan generation."""

from __future__ import annotations

import argparse
import os
from typing import Any, Dict

import torch
from datasets import load_dataset
from peft import LoraConfig
from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments
from trl import SFTTrainer


def _format_row(example: Dict[str, Any], tokenizer: AutoTokenizer) -> Dict[str, str]:
    if getattr(tokenizer, "chat_template", None):
        text = tokenizer.apply_chat_template(
            example["messages"],
            tokenize=False,
            add_generation_prompt=False,
        )
    else:
        chunks = [f"{m['role'].upper()}: {m['content']}" for m in example["messages"]]
        text = "\n".join(chunks)
    return {"text": text}


def _target_modules(model_name: str) -> str | list[str]:
    lower = model_name.lower()
    if "gpt2" in lower:
        return ["c_attn", "c_proj"]
    if "gpt-oss" in lower or "gpt_oss" in lower:
        return "all-linear"
    return ["q_proj", "k_proj", "v_proj", "o_proj", "up_proj", "down_proj", "gate_proj"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fine-tune planner model with LoRA.")
    parser.add_argument("--model-name", type=str, default="openai/gpt-oss-20b")
    parser.add_argument("--train-file", type=str, default="data/processed/sft_train.jsonl")
    parser.add_argument("--val-file", type=str, default="data/processed/sft_val.jsonl")
    parser.add_argument("--output-dir", type=str, default="data/models/android-lora-planner")
    parser.add_argument("--max-seq-length", type=int, default=2048)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--grad-accum", type=int, default=8)
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--use-bf16", action="store_true")
    parser.add_argument("--target-modules", nargs="+", default=None)
    parser.add_argument("--trust-remote-code", action="store_true")
    parser.add_argument("--cache-dir", type=str, default="data/cache/huggingface")
    args = parser.parse_args(argv)

    if not os.path.exists(args.train_file) or not os.path.exists(args.val_file):
        raise ValueError("SFT files missing. Run scripts/build_sft_dataset.py first.")

    os.makedirs(args.cache_dir, exist_ok=True)
    os.environ.setdefault("HF_HOME", args.cache_dir)
    os.environ.setdefault("HF_DATASETS_CACHE", args.cache_dir)
    os.environ.setdefault("TRANSFORMERS_CACHE", args.cache_dir)

    dataset = load_dataset(
        "json",
        data_files={"train": args.train_file, "validation": args.val_file},
        cache_dir=args.cache_dir,
    )

    tokenizer = AutoTokenizer.from_pretrained(
        args.model_name,
        use_fast=True,
        cache_dir=args.cache_dir,
        trust_remote_code=args.trust_remote_code,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.model_max_length = args.max_seq_length

    remove_cols = list(dataset["train"].column_names)
    formatted = dataset.map(
        lambda row: {"text": _format_row(row, tokenizer)["text"]},
        remove_columns=remove_cols,
    )

    has_cuda = torch.cuda.is_available()
    dtype = torch.bfloat16 if args.use_bf16 else (torch.float16 if has_cuda else torch.float32)

    model = AutoModelForCausalLM.from_pretrained(
        args.model_name,
        torch_dtype=dtype,
        device_map="auto" if has_cuda else None,
        cache_dir=args.cache_dir,
        trust_remote_code=args.trust_remote_code,
    )

    target_modules = args.target_modules or _target_modules(args.model_name)
    if target_modules == ["all-linear"]:
        target_modules = "all-linear"

    peft_config = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        bias="none",
        target_modules=target_modules,
        task_type="CAUSAL_LM",
    )

    training_args = TrainingArguments(
        output_dir=args.output_dir,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.learning_rate,
        lr_scheduler_type="cosine",
        warmup_ratio=0.05,
        logging_steps=10,
        eval_strategy="steps",
        eval_steps=50,
        save_strategy="steps",
        save_steps=50,
        save_total_limit=2,
        bf16=args.use_bf16 and has_cuda,
        fp16=(not args.use_bf16) and has_cuda,
        gradient_checkpointing=True,
        report_to="none",
    )

    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=formatted["train"],
        eval_dataset=formatted["validation"],
        processing_class=tokenizer,
        peft_config=peft_config,
    )

    trainer.train()
    trainer.save_model(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)

    print(f"Saved LoRA planner to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
